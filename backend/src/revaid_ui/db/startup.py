"""Viewer-owned startup reconciliation against the analysis HTTP API."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from revaid_contracts.analysis import AnalysisClient
from revaid_contracts.clock import utc_now_iso
from revaid_contracts.logging import get_logger
from revaid_ui.db.models import BinaryUiState, View, ViewNode

logger = get_logger(__name__)


async def reconcile_viewer_state(analysis: AnalysisClient, viewer_session: AsyncSession) -> int:
    """Remove stale viewer references to binaries/functions deleted in analysis."""
    states = list((await viewer_session.execute(select(BinaryUiState))).scalars())
    view_ids = {state.last_view_id for state in states if state.last_view_id is not None}
    view_owners: dict[int, int] = {}
    if view_ids:
        result = await viewer_session.execute(
            select(View.id, View.binary_id).where(View.id.in_(view_ids))
        )
        view_owners = {view_id: binary_id for view_id, binary_id in result.all()}

    changed = 0
    for state in states:
        if (
            state.last_view_id is not None
            and view_owners.get(state.last_view_id) != state.binary_id
        ):
            state.last_view_id = None
            changed += 1

    views = list((await viewer_session.execute(select(View))).scalars())
    stale_view_ids: list[int] = []
    checked_binary_ids: dict[int, bool] = {}
    for view in views:
        if view.binary_id not in checked_binary_ids:
            checked_binary_ids[view.binary_id] = (
                await analysis.get_binary(view.binary_id) is not None
            )
        if not checked_binary_ids[view.binary_id]:
            stale_view_ids.append(view.id)
    if stale_view_ids:
        await viewer_session.execute(delete(View).where(View.id.in_(stale_view_ids)))

    valid_view_ids = {view.id for view in views if view.id not in stale_view_ids}
    checked_state_binary_ids = {view.binary_id for view in views}
    for state in states:
        if state.binary_id not in checked_state_binary_ids:
            checked_state_binary_ids.add(state.binary_id)
            if await analysis.get_binary(state.binary_id) is None:
                await viewer_session.delete(state)
                changed += 1

    for view in views:
        if view.id not in valid_view_ids:
            continue
        nodes = list(
            (
                await viewer_session.execute(select(ViewNode).where(ViewNode.view_id == view.id))
            ).scalars()
        )
        stale_nodes_changed = False
        if view.root_function_id is not None:
            valid_root = await analysis.validate_function_membership(
                view.binary_id, [view.root_function_id]
            )
            if view.root_function_id not in valid_root:
                view.root_function_id = None
                changed += 1
        ids = sorted(
            {
                function_id
                for node in nodes
                for function_id in (node.function_id, node.origin_function_id)
                if function_id is not None
            }
        )
        valid_ids: set[int] = set()
        for start in range(0, len(ids), 500):
            valid_ids.update(
                await analysis.validate_function_membership(
                    view.binary_id, ids[start : start + 500]
                )
            )
        for node in nodes:
            if node.function_id not in valid_ids:
                await viewer_session.delete(node)
                changed += 1
                stale_nodes_changed = True
            elif node.origin_function_id is not None and node.origin_function_id not in valid_ids:
                node.origin_function_id = None
                node.origin_kind = "root"
                node.origin_implied = False
                changed += 1
                stale_nodes_changed = True
        if stale_nodes_changed:
            view.updated_at = utc_now_iso()
        if view.root_function_id is None and nodes:
            visible_roots = [
                node
                for node in nodes
                if node.function_id in valid_ids
                and node.visible
                and node.origin_function_id is None
            ]
            if visible_roots:
                view.root_function_id = visible_roots[0].function_id
                view.updated_at = utc_now_iso()
                changed += 1

    if changed or stale_view_ids:
        await viewer_session.commit()
        logger.info(
            "startup.reconciled_viewer_canvas", changed=changed, deleted_views=len(stale_view_ids)
        )
    return changed + len(stale_view_ids)
