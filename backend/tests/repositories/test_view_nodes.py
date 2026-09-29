"""Viewer `repositories/view_nodes.py` batch upsert/remove behavior."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from revaid_contracts.clock import utc_now_iso
from revaid_ui.db.models import View
from revaid_ui.repositories.view_nodes import (
    list_nodes_by_view,
    remove_view_nodes,
    upsert_view_nodes,
)


async def _make_view(
    session: AsyncSession, *, binary_id: int = 98765, name: str = "Default"
) -> View:
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
    session.add(view)
    await session.flush()
    return view


@pytest.mark.asyncio
async def test_upsert_creates_row_with_defaults_for_omitted_fields(
    viewer_session: AsyncSession,
) -> None:
    view = await _make_view(viewer_session)
    await upsert_view_nodes(
        viewer_session, view_id=view.id, upserts=[{"function_id": 12345, "pos_x": 12.0}]
    )
    await viewer_session.commit()

    nodes = await list_nodes_by_view(viewer_session, view_id=view.id)
    assert len(nodes) == 1
    node = nodes[0]
    assert node.function_id == 12345
    assert node.pos_x == 12.0
    assert node.pos_y == 0.0
    assert node.visible is True
    assert node.collapsed is False
    assert node.pinned is False
    assert node.origin_kind == "root"
    assert node.origin_function_id is None
    assert node.origin_implied is False


@pytest.mark.asyncio
async def test_upsert_updates_existing_row_dedup_on_view_and_function(
    viewer_session: AsyncSession,
) -> None:
    view = await _make_view(viewer_session)
    await upsert_view_nodes(
        viewer_session,
        view_id=view.id,
        upserts=[{"function_id": 12345, "pos_x": 1.0, "pinned": False}],
    )
    await viewer_session.commit()
    await upsert_view_nodes(
        viewer_session,
        view_id=view.id,
        upserts=[{"function_id": 12345, "pos_x": 99.0, "pinned": True}],
    )
    await viewer_session.commit()

    nodes = await list_nodes_by_view(viewer_session, view_id=view.id)
    assert len(nodes) == 1
    assert nodes[0].pos_x == 99.0
    assert nodes[0].pinned is True


@pytest.mark.asyncio
async def test_upsert_partial_patch_leaves_omitted_fields_untouched(
    viewer_session: AsyncSession,
) -> None:
    view = await _make_view(viewer_session)
    await upsert_view_nodes(
        viewer_session,
        view_id=view.id,
        upserts=[{"function_id": 12345, "pos_x": 1.0, "pos_y": 2.0}],
    )
    await viewer_session.commit()
    await upsert_view_nodes(
        viewer_session, view_id=view.id, upserts=[{"function_id": 12345, "pos_x": 5.0}]
    )
    await viewer_session.commit()

    nodes = await list_nodes_by_view(viewer_session, view_id=view.id)
    assert nodes[0].pos_x == 5.0
    assert nodes[0].pos_y == 2.0


@pytest.mark.asyncio
async def test_remove_is_scoped_to_the_given_view(viewer_session: AsyncSession) -> None:
    view_a = await _make_view(viewer_session, name="A")
    view_b = await _make_view(viewer_session, name="B")
    await upsert_view_nodes(viewer_session, view_id=view_a.id, upserts=[{"function_id": 12345}])
    await upsert_view_nodes(viewer_session, view_id=view_b.id, upserts=[{"function_id": 12345}])
    await viewer_session.commit()

    await remove_view_nodes(viewer_session, view_id=view_a.id, function_ids=[12345])
    await viewer_session.commit()

    assert await list_nodes_by_view(viewer_session, view_id=view_a.id) == []
    assert len(await list_nodes_by_view(viewer_session, view_id=view_b.id)) == 1


@pytest.mark.asyncio
async def test_remove_with_empty_list_is_a_noop(viewer_session: AsyncSession) -> None:
    view = await _make_view(viewer_session)
    await upsert_view_nodes(viewer_session, view_id=view.id, upserts=[{"function_id": 12345}])
    await viewer_session.commit()

    await remove_view_nodes(viewer_session, view_id=view.id, function_ids=[])
    await viewer_session.commit()

    assert len(await list_nodes_by_view(viewer_session, view_id=view.id)) == 1
