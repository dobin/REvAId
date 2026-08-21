"""Function repository: idempotent UPSERT (A3) + fan-in/fan-out/utility recompute.

``INGESTION_OWNED_COLUMNS`` is re-exported here so
``graphrev.repositories.functions.INGESTION_OWNED_COLUMNS`` is the stable
import path callers use, even though the frozenset itself is defined next to
the model it guards (``db/models.py``).
"""

from __future__ import annotations

import json

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.enums import FunctionKind
from graphrev.db.models import INGESTION_OWNED_COLUMNS, Function

__all__ = [
    "INGESTION_OWNED_COLUMNS",
    "get_function_by_id",
    "list_entry_points",
    "recompute_fan_in_fan_out_and_utility",
    "resolve_function_by_address",
    "search_functions",
    "upsert_function",
]

#: Columns present in the INSERT's VALUES that are NOT part of
#: ``INGESTION_OWNED_COLUMNS`` and must therefore be supplied only on first
#: insert, never touched again on conflict (the primary key, the creation
#: timestamp, and ``is_entry_point`` — analyst-owned like
#: ``utility_override``, seeded by the adapter but sticky thereafter).
_INSERT_ONLY_COLUMNS = frozenset({"id", "created_at", "is_entry_point"})


async def upsert_function(
    session: AsyncSession,
    *,
    binary_id: int,
    address: int,
    name_ghidra: str,
    parameters: list[dict[str, object]] | None = None,
    signature: str | None = None,
    assembly: str | None = None,
    code_c: str | None = None,
    kind: FunctionKind = "normal",
    placeholder_module: str | None = None,
    is_entry_point: bool = False,
) -> tuple[int, bool]:
    """Idempotent UPSERT keyed on ``(binary_id, address)`` (``ux_functions_binary_address``).

    On conflict, only the columns in ``INGESTION_OWNED_COLUMNS`` are
    overwritten — ``summary_*``, ``name_analyst``, ``notes``,
    ``notes_updated_at``, ``utility_override``, ``is_entry_point`` are never
    referenced in the UPDATE SET clause, which is generated from the
    frozenset itself so a future column addition to
    ``INGESTION_OWNED_COLUMNS`` cannot silently fail to reach this UPSERT.
    ``is_entry_point`` is written only on first INSERT (I3/E1b): the adapter
    may flag a function as an entry point at discovery time, but the value
    is analyst-owned thereafter, exactly like ``utility_override``.

    Returns ``(function_id, created)``.
    """
    existing_id = (
        await session.execute(
            select(Function.id).where(Function.binary_id == binary_id, Function.address == address)
        )
    ).scalar_one_or_none()
    created = existing_id is None

    now = utc_now_iso()
    values: dict[str, object] = {
        "binary_id": binary_id,
        "address": address,
        "name_ghidra": name_ghidra,
        "parameters": json.dumps(parameters or []),
        "signature": signature,
        "assembly": assembly,
        "code_c": code_c,
        "kind": kind,
        "placeholder_module": placeholder_module,
        "is_entry_point": is_entry_point,
        "created_at": now,
        "updated_at": now,
    }

    # The UPDATE SET clause is exactly ``INGESTION_OWNED_COLUMNS`` (the A3
    # guard) minus columns that only make sense at insert time.
    update_columns = INGESTION_OWNED_COLUMNS - _INSERT_ONLY_COLUMNS

    stmt = sqlite_insert(Function).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Function.binary_id, Function.address],
        set_={col: stmt.excluded[col] for col in update_columns if col in values},
    )
    result = await session.execute(stmt.returning(Function.id))
    function_id = result.scalar_one()
    await session.flush()

    return function_id, created


async def recompute_fan_in_fan_out_and_utility(
    session: AsyncSession, *, binary_id: int, threshold: int
) -> None:
    """A7a/F1b: recompute ``fan_in``, ``fan_out``, and ``is_utility`` for one binary.

    ``fan_in``/``fan_out`` are distinct-caller/-callee counts over ``edges``.
    ``is_utility``'s formula (``fan_in > threshold``) is intentionally
    identical, textually, to
    ``graphrev.db.startup.recompute_utility_if_threshold_changed``'s raw-SQL
    recompute and to ``classification.utility.is_utility`` — all three must
    be kept in lockstep if the classifier ever changes (TQ5).
    """
    await session.execute(
        text(
            """
            UPDATE functions
            SET fan_in = (
                SELECT COUNT(DISTINCT e.caller_id)
                FROM edges e
                WHERE e.callee_id = functions.id
            )
            WHERE functions.binary_id = :binary_id
            """
        ),
        {"binary_id": binary_id},
    )
    await session.execute(
        text(
            """
            UPDATE functions
            SET fan_out = (
                SELECT COUNT(DISTINCT e.callee_id)
                FROM edges e
                WHERE e.caller_id = functions.id
            )
            WHERE functions.binary_id = :binary_id
            """
        ),
        {"binary_id": binary_id},
    )
    await session.execute(
        text(
            "UPDATE functions SET is_utility = (fan_in > :threshold) WHERE binary_id = :binary_id"
        ),
        {"threshold": threshold, "binary_id": binary_id},
    )
    await session.flush()


async def get_function_by_id(session: AsyncSession, function_id: int) -> Function | None:
    """A single `Function` row by id, or `None` if it does not exist (E1)."""
    return await session.get(Function, function_id)


async def search_functions(
    session: AsyncSession,
    *,
    binary_id: int,
    query: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Function], int]:
    """Paginated, case-insensitive substring search over a binary's functions
    (B11/E1a).

    Matches `name_ghidra`, `name_analyst`, or `notes` via
    ``LIKE '%q%' COLLATE NOCASE`` (TAD §3.3 design note — an FTS5 upgrade is
    an additive M1 item, TQ1). Returns `(page, total)`; `total` is the count
    across the whole match set, not just the returned page, so the caller
    can render "showing N of TOTAL".
    """
    filters = [Function.binary_id == binary_id]
    if query:
        like = f"%{query}%"
        filters.append(
            or_(
                Function.name_ghidra.collate("NOCASE").like(like),
                Function.name_analyst.collate("NOCASE").like(like),
                Function.notes.collate("NOCASE").like(like),
            )
        )

    base_stmt = select(Function).where(*filters)
    total = (
        await session.execute(select(func.count()).select_from(base_stmt.subquery()))
    ).scalar_one()

    page_stmt = (
        base_stmt.order_by(Function.name_ghidra.asc(), Function.id.asc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(page_stmt)).scalars().all()
    return list(rows), total


async def resolve_function_by_address(
    session: AsyncSession, *, binary_id: int, address: int
) -> Function | None:
    """Resolve `address` to its containing function (D2).

    No function has a persisted end-address/size in M0 (TAD §4.3 note), so
    this uses the nearest-at-or-before heuristic: the function in `binary_id`
    with the greatest `address` that is `<= address`. Returns `None` if
    `address` is before every function in the binary (or the binary has no
    functions) — the caller maps that to `ADDRESS_UNRESOLVED`.
    """
    result = await session.execute(
        select(Function)
        .where(Function.binary_id == binary_id, Function.address <= address)
        .order_by(Function.address.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_entry_points(session: AsyncSession, *, binary_id: int, limit: int) -> list[Function]:
    """Up to `limit` entry-point-flagged functions for a binary (E1b),
    ordered by `fan_out` descending (the ones most likely to be useful
    starting points for an empty canvas)."""
    result = await session.execute(
        select(Function)
        .where(Function.binary_id == binary_id, Function.is_entry_point.is_(True))
        .order_by(Function.fan_out.desc(), Function.id.asc())
        .limit(limit)
    )
    return list(result.scalars().all())
