"""Function repository: idempotent UPSERT (A3) + fan-in/fan-out/utility recompute.

``INGESTION_OWNED_COLUMNS`` is re-exported here so
``graphrev.repositories.functions.INGESTION_OWNED_COLUMNS`` is the stable
import path callers use, even though the frozenset itself is defined next to
the model it guards (``db/models.py``).
"""

from __future__ import annotations

import json
from typing import TypedDict

from sqlalchemy import String, cast, func, or_, select, text
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
    "upsert_functions_batch",
]


class FunctionBatchValues(TypedDict, total=False):
    """Ingestion-owned inputs accepted by :func:`upsert_functions_batch`."""

    address: int
    name_ghidra: str
    parameters: list[dict[str, object]]
    signature: str | None
    assembly: str | None
    code_c: str | None
    kind: FunctionKind
    placeholder_module: str | None
    has_indirect_calls: bool
    is_entry_point: bool

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
    has_indirect_calls: bool = False,
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
        "has_indirect_calls": has_indirect_calls,
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


async def upsert_functions_batch(
    session: AsyncSession,
    *,
    binary_id: int,
    functions: list[FunctionBatchValues],
) -> tuple[dict[int, int], int, int]:
    """Upsert a bounded group of ingestion rows in one SQLite statement.

    Returns ``(address_to_id, inserted, updated)``. Callers must provide
    unique addresses inside a batch. The prior address lookup provides exact
    counts without the former SELECT-per-function cost; the conflict update
    intentionally retains the same A3 protected-column rule as
    :func:`upsert_function`.
    """
    if not functions:
        return {}, 0, 0

    addresses = [int(row["address"]) for row in functions]
    existing_addresses = set(
        (
            await session.execute(
                select(Function.address).where(
                    Function.binary_id == binary_id, Function.address.in_(addresses)
                )
            )
        ).scalars()
    )
    now = utc_now_iso()
    values: list[dict[str, object]] = [
        {
            "binary_id": binary_id,
            "address": int(row["address"]),
            "name_ghidra": str(row["name_ghidra"]),
            "parameters": json.dumps(row.get("parameters", [])),
            "signature": row.get("signature"),
            "assembly": row.get("assembly"),
            "code_c": row.get("code_c"),
            "kind": row.get("kind", "normal"),
            "placeholder_module": row.get("placeholder_module"),
            "has_indirect_calls": bool(row.get("has_indirect_calls", False)),
            "is_entry_point": bool(row.get("is_entry_point", False)),
            "created_at": now,
            "updated_at": now,
        }
        for row in functions
    ]
    update_columns = INGESTION_OWNED_COLUMNS - _INSERT_ONLY_COLUMNS
    stmt = sqlite_insert(Function).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Function.binary_id, Function.address],
        set_={col: stmt.excluded[col] for col in update_columns if col in values[0]},
    )
    await session.execute(stmt)
    rows = (
        await session.execute(
            select(Function.address, Function.id).where(
                Function.binary_id == binary_id, Function.address.in_(addresses)
            )
        )
    ).all()
    address_to_id = {row.address: row.id for row in rows}
    inserted = sum(address not in existing_addresses for address in addresses)
    return address_to_id, inserted, len(addresses) - inserted


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


async def update_utility_override(
    session: AsyncSession, *, function_id: int, utility_override: str | None
) -> Function | None:
    """D36/E2c: set (or clear, via `None`) the analyst's utility override.

    Returns the updated `Function` row, or `None` if `function_id` does not
    exist. This is the *only* write path the D36 override goes through —
    ingestion never touches it (`utility_override` is in
    `INGESTION_OWNED_COLUMNS`'s complement, guarded by the A3 test).
    """
    fn = await session.get(Function, function_id)
    if fn is None:
        return None
    fn.utility_override = utility_override
    fn.updated_at = utc_now_iso()
    await session.flush()
    # `is_utility_effective` is a DB-computed GENERATED column: SQLAlchemy
    # marks it expired after the UPDATE flush, and a bare attribute access
    # later (e.g. in `function_dto_from_row`) would trigger an implicit
    # lazy-load — which raises `MissingGreenlet` under the async driver, since
    # nothing here awaits it. Refresh eagerly, inside this async context,
    # instead.
    await session.refresh(fn, attribute_names=["is_utility_effective"])
    return fn


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

    Matches `name_ghidra`, `name_llm`, `name_analyst`, `notes`, or `address` via
    ``LIKE '%q%' COLLATE NOCASE`` (TAD §3.3 design note — an FTS5 upgrade is
    an additive M1 item, TQ1). The address match is substring-based against
    both the decimal and hex (`0x`-stripped) renderings of `address`, so a
    query like `1000` or `0x1000` finds function `0x00401000`. Returns
    `(page, total)`; `total` is the count across the whole match set, not
    just the returned page, so the caller can render "showing N of TOTAL".
    """
    filters = [Function.binary_id == binary_id]
    if query:
        like = f"%{query}%"
        address_query = query.strip()
        if address_query.lower().startswith("0x"):
            address_query = address_query[2:]
        filters.append(
            or_(
                Function.name_ghidra.collate("NOCASE").like(like),
                Function.name_llm.collate("NOCASE").like(like),
                Function.name_analyst.collate("NOCASE").like(like),
                Function.notes.collate("NOCASE").like(like),
                cast(Function.address, String).like(like),
                func.printf("%X", Function.address).like(f"%{address_query.upper()}%"),
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
