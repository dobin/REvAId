"""Viewer view initialization and featured-graph placement helpers."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revaid_contracts.clock import utc_now_iso
from revaid_contracts.ids import random_view_id
from revaid_ui.core.config import get_settings
from revaid_ui.db.models import View, ViewNode


def seed_view_from_analysis(
    session: AsyncSession,
    view: View,
    *,
    featured_ids: list[int],
    call_pairs: list[tuple[int, int]],
) -> None:
    """Place an analysis-provided featured graph using a deterministic forest."""
    if not featured_ids:
        return

    rank = {function_id: index for index, function_id in enumerate(featured_ids)}
    adjacency: dict[int, list[tuple[int, str]]] = {function_id: [] for function_id in featured_ids}
    for caller_id, callee_id in call_pairs:
        if caller_id == callee_id:
            continue
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
                if function_id not in provenance:
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
    if get_settings().public_mode:
        for _attempt in range(3):
            try:
                view.id = random_view_id()
                session.add(view)
                await session.flush()
                return view
            except IntegrityError:
                await session.rollback()
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
    session.add(view)
    await session.flush()
    return view
