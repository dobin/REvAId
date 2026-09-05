"""Edge repository: idempotent insert with pair-dedup (B3).

Duplicate `(caller_id, callee_id)` pairs are silently skipped
(`ux_edges_pair`); self-edges (recursion) are allowed.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import case, select, tuple_
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.db.enums import EdgeKind
from graphrev.db.models import Edge


@dataclass(frozen=True, slots=True)
class EdgeUpsertValues:
    """One distinct edge and optional ingestion-owned static callee order."""

    caller_id: int
    callee_id: int
    callee_order: int | None = None


async def upsert_edge(
    session: AsyncSession,
    *,
    binary_id: int,
    caller_id: int,
    callee_id: int,
    callee_order: int | None = None,
    kind: EdgeKind = "call",
) -> bool:
    """Insert one edge or refresh its non-null imported order.

    Returns `True` if a new row was inserted, `False` if the pair already
    existed. An order-less legacy source never erases a known order.
    """
    existing = await session.scalar(
        select(Edge.id).where(Edge.caller_id == caller_id, Edge.callee_id == callee_id)
    )
    insert_stmt = sqlite_insert(Edge)
    stmt = insert_stmt.values(
        binary_id=binary_id,
        caller_id=caller_id,
        callee_id=callee_id,
        callee_order=callee_order,
        kind=kind,
    ).on_conflict_do_update(
        index_elements=[Edge.caller_id, Edge.callee_id],
        set_={
            "callee_order": case(
                (insert_stmt.excluded.callee_order.is_not(None), insert_stmt.excluded.callee_order),
                else_=Edge.callee_order,
            )
        },
    )
    await session.execute(stmt)
    await session.flush()
    return existing is None


async def upsert_edges_batch(
    session: AsyncSession,
    *,
    binary_id: int,
    edges: list[EdgeUpsertValues],
    kind: EdgeKind = "call",
) -> tuple[int, int]:
    """Insert unique edge pairs or refresh their non-null imported order.

    Returns ``(inserted, skipped_duplicate)``. Database uniqueness remains
    authoritative for duplicates already persisted by an earlier import.
    """
    by_pair: dict[tuple[int, int], EdgeUpsertValues] = {}
    for edge in edges:
        pair = (edge.caller_id, edge.callee_id)
        existing = by_pair.get(pair)
        if existing is not None and existing.callee_order != edge.callee_order:
            raise ValueError(f"conflicting callee_order values for edge {pair}")
        by_pair[pair] = edge
    values = list(by_pair.values())
    if not values:
        return 0, 0
    pairs = [(edge.caller_id, edge.callee_id) for edge in values]
    existing_pairs = set(
        (
            await session.execute(
                select(Edge.caller_id, Edge.callee_id).where(
                    tuple_(Edge.caller_id, Edge.callee_id).in_(pairs)
                )
            )
        ).all()
    )
    insert_stmt = sqlite_insert(Edge)
    stmt = insert_stmt.values(
        [
            {
                "binary_id": binary_id,
                "caller_id": edge.caller_id,
                "callee_id": edge.callee_id,
                "callee_order": edge.callee_order,
                "kind": kind,
            }
            for edge in values
        ]
    ).on_conflict_do_update(
        index_elements=[Edge.caller_id, Edge.callee_id],
        set_={
            "callee_order": case(
                (insert_stmt.excluded.callee_order.is_not(None), insert_stmt.excluded.callee_order),
                else_=Edge.callee_order,
            )
        },
    )
    await session.execute(stmt)
    inserted = len(pairs) - len(existing_pairs)
    return inserted, len(edges) - inserted
