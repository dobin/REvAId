"""Binary repository: idempotent lookup-or-create (A1, A7) + I3 read/delete.

A binary is uniquely identified by `(name, version)` (`ux_binaries_name_version`).
Re-ingesting the same binary must not create a duplicate row and must never
touch `last_view_id` (B16 — owned by the view-switching UI, not ingestion).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Binary, Edge, Function


async def get_or_create_binary(
    session: AsyncSession,
    *,
    name: str,
    version: str,
    source_path: str | None = None,
) -> tuple[Binary, bool]:
    """Return the `Binary` row for `(name, version)`, creating it if absent.

    Returns `(binary, created)`. On an existing row, only `updated_at` and
    `source_path` are refreshed — `last_view_id` is never written here.
    """
    result = await session.execute(
        select(Binary).where(Binary.name == name, Binary.version == version)
    )
    existing = result.scalar_one_or_none()
    now = utc_now_iso()

    if existing is not None:
        existing.source_path = source_path
        existing.updated_at = now
        await session.flush()
        return existing, False

    binary = Binary(
        name=name,
        version=version,
        source_path=source_path,
        created_at=now,
        updated_at=now,
    )
    session.add(binary)
    await session.flush()
    return binary, True


@dataclass(frozen=True, slots=True)
class BinaryWithCounts:
    """A `Binary` row plus its function/edge counts (E1's `BinarySummaryDto`)."""

    binary: Binary
    function_count: int
    edge_count: int


async def list_binaries(session: AsyncSession) -> list[BinaryWithCounts]:
    """All binaries with their function/edge counts (E1), ordered by name.

    Two scalar subquery counts per row rather than a `GROUP BY` join —
    `binaries` is small (single-user, at most a handful of ingested
    binaries), so a correlated-subquery `SELECT` is simpler than
    reconciling two independent one-to-many joins (`functions`, `edges`)
    in a single `GROUP BY` without a fan-out row-count bug.
    """
    function_count_subq = (
        select(func.count(Function.id)).where(Function.binary_id == Binary.id).scalar_subquery()
    )
    edge_count_subq = (
        select(func.count(Edge.id)).where(Edge.binary_id == Binary.id).scalar_subquery()
    )
    result = await session.execute(
        select(Binary, function_count_subq, edge_count_subq).order_by(Binary.name, Binary.version)
    )
    return [
        BinaryWithCounts(binary=binary, function_count=fn_count, edge_count=edge_count)
        for binary, fn_count, edge_count in result.all()
    ]


async def get_binary_by_id(session: AsyncSession, binary_id: int) -> Binary | None:
    """A single `Binary` row by id, or `None` if it does not exist."""
    return await session.get(Binary, binary_id)


async def delete_binary(session: AsyncSession, binary: Binary) -> None:
    """Delete a binary; cascades to functions/edges/views/view_nodes via the
    DB-level `ON DELETE CASCADE` foreign keys (`passive_deletes=True` on the
    ORM relationships, so the ORM does not also try to load and delete every
    child row itself)."""
    await session.delete(binary)
    await session.flush()
