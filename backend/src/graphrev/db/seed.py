"""View seeding helpers (B9 and operator-curated featured functions).

Written now, called by the ingestion pipeline in I2: every binary must have at
least one view so the picker is never empty after ingestion.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.core.config import get_settings
from graphrev.core.ids import random_view_id
from graphrev.db.models import Edge, Function, View, ViewNode


async def seed_featured_view_nodes(session: AsyncSession, view: View) -> None:
    """Copy this binary's featured functions into a newly created view.

    Featured membership is a creation-time template, not a live link: once
    these rows exist, normal view edits are authoritative. Known calls among
    featured functions become a deterministic provenance spanning forest so
    the frontend derives edges and ELK lays out each connected component.
    """
    featured_ids = list(
        (
            await session.execute(
                select(Function.id)
                .where(Function.binary_id == view.binary_id, Function.is_featured.is_(True))
                .order_by(Function.address, Function.id)
            )
        ).scalars()
    )
    if not featured_ids:
        return

    rank = {function_id: index for index, function_id in enumerate(featured_ids)}
    featured_set = set(featured_ids)
    call_pairs = list(
        (
            await session.execute(
                select(Edge.caller_id, Edge.callee_id).where(
                    Edge.kind == "call",
                    Edge.caller_id.in_(featured_set),
                    Edge.callee_id.in_(featured_set),
                )
            )
        ).all()
    )
    adjacency: dict[int, list[tuple[int, str]]] = {
        function_id: [] for function_id in featured_ids
    }
    for caller_id, callee_id in call_pairs:
        if caller_id == callee_id:
            continue
        # The child stores the already-placed node as its origin. `fanout`
        # means origin calls child; `fanin` means child calls origin.
        adjacency[caller_id].append((callee_id, "fanout"))
        adjacency[callee_id].append((caller_id, "fanin"))
    for neighbours in adjacency.values():
        neighbours.sort(key=lambda item: rank[item[0]])

    provenance: dict[int, tuple[int | None, str]] = {}
    for component_root in featured_ids:
        if component_root in provenance:
            continue
        provenance[component_root] = (None, "root")
        queue = [component_root]
        while queue:
            origin_id = queue.pop(0)
            for function_id, origin_kind in adjacency[origin_id]:
                if function_id in provenance:
                    continue
                provenance[function_id] = (origin_id, origin_kind)
                queue.append(function_id)

    now = utc_now_iso()
    view.root_function_id = featured_ids[0]
    view.updated_at = now
    session.add_all(
        [
            ViewNode(
                view_id=view.id,
                function_id=function_id,
                visible=True,
                collapsed=False,
                color=None,
                pos_x=0.0,
                pos_y=0.0,
                pinned=False,
                origin_function_id=provenance[function_id][0],
                origin_kind=provenance[function_id][1],
                origin_implied=False,
                created_at=now,
                updated_at=now,
            )
            for function_id in featured_ids
        ]
    )
    await session.flush()


async def create_default_view(session: AsyncSession, binary_id: int, name: str = "Default") -> View:
    now = utc_now_iso()
    view = View(
        binary_id=binary_id,
        name=name,
        root_function_id=None,
        camera_x=0.0,
        camera_y=0.0,
        camera_zoom=1.0,
        created_at=now,
        updated_at=now,
    )
    # ADR 0006: in public mode the seeded default view is still a shared
    # reference point for the *owner*, so its id must not be enumerable
    # either. Randomize it up front so enabling public mode on a fresh DB
    # never leaves guessable low-id views behind.
    if get_settings().public_mode:
        for _attempt in range(3):
            try:
                view.id = random_view_id()
                session.add(view)
                await session.flush()
                await seed_featured_view_nodes(session, view)
                return view
            except IntegrityError:
                await session.rollback()
                # Rebuild a fresh View — the failed flush invalidated the
                # previous instance's insert state.
                view = View(
                    binary_id=binary_id,
                    name=name,
                    root_function_id=None,
                    camera_x=0.0,
                    camera_y=0.0,
                    camera_zoom=1.0,
                    created_at=now,
                    updated_at=now,
                )
        # Vanishingly rare (2^53 space); fall back to autoincrement rather
        # than failing ingestion outright.
    session.add(view)
    await session.flush()
    await seed_featured_view_nodes(session, view)
    return view
