"""Edge repository: idempotent insert with pair-dedup (B3).

Duplicate `(caller_id, callee_id)` pairs are silently skipped
(`ux_edges_pair`); self-edges (recursion) are allowed.
"""

from __future__ import annotations

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.db.enums import EdgeKind
from graphrev.db.models import Edge


async def upsert_edge(
    session: AsyncSession,
    *,
    binary_id: int,
    caller_id: int,
    callee_id: int,
    kind: EdgeKind = "call",
) -> bool:
    """Insert one edge; a duplicate `(caller_id, callee_id)` pair is a no-op.

    Returns `True` if a new row was inserted, `False` if the pair already
    existed.
    """
    stmt = (
        sqlite_insert(Edge)
        .values(binary_id=binary_id, caller_id=caller_id, callee_id=callee_id, kind=kind)
        .on_conflict_do_nothing(index_elements=[Edge.caller_id, Edge.callee_id])
        .returning(Edge.id)
    )
    result = await session.execute(stmt)
    inserted_id = result.scalar_one_or_none()
    await session.flush()
    return inserted_id is not None


async def upsert_edges_batch(
    session: AsyncSession,
    *,
    binary_id: int,
    edges: list[tuple[int, int]],
    kind: EdgeKind = "call",
) -> tuple[int, int]:
    """Insert unique edge pairs in one bounded statement.

    Returns ``(inserted, skipped_duplicate)``. Database uniqueness remains
    authoritative for duplicates already persisted by an earlier import.
    """
    pairs = list(dict.fromkeys(edges))
    if not pairs:
        return 0, 0
    stmt = (
        sqlite_insert(Edge)
        .values(
            [
                {
                    "binary_id": binary_id,
                    "caller_id": caller_id,
                    "callee_id": callee_id,
                    "kind": kind,
                }
                for caller_id, callee_id in pairs
            ]
        )
        .on_conflict_do_nothing(index_elements=[Edge.caller_id, Edge.callee_id])
        .returning(Edge.id)
    )
    inserted = len((await session.execute(stmt)).scalars().all())
    return inserted, len(edges) - inserted
