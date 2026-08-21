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
