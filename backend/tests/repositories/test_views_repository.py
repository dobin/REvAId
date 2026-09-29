"""Viewer `repositories/views.py` CRUD behavior."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from revaid_contracts.clock import utc_now_iso
from revaid_ui.db.models import BinaryUiState, View
from revaid_ui.repositories.view_nodes import upsert_view_nodes
from revaid_ui.repositories.views import (
    clear_last_view_ids_for_view,
    count_views_by_binary,
    create_view,
    delete_view,
    duplicate_view,
    get_last_view_ids,
    get_view_by_id,
    list_views_by_binary,
    set_last_view_id,
    set_root_function_id,
    update_view_fields,
)


async def _make_view(session: AsyncSession, *, binary_id: int, name: str) -> View:
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
async def test_list_views_by_binary_returns_only_that_binarys_views(
    viewer_session: AsyncSession,
) -> None:
    await _make_view(viewer_session, binary_id=100, name="A")
    await _make_view(viewer_session, binary_id=200, name="B")
    await viewer_session.commit()
    views = await list_views_by_binary(viewer_session, binary_id=100)
    assert len(views) == 1 and views[0].binary_id == 100


@pytest.mark.asyncio
async def test_list_views_empty_for_binary_with_no_views(viewer_session: AsyncSession) -> None:
    assert await list_views_by_binary(viewer_session, binary_id=100) == []


@pytest.mark.asyncio
async def test_list_views_by_binary_orders_by_id(viewer_session: AsyncSession) -> None:
    first = await _make_view(viewer_session, binary_id=100, name="First")
    second = await _make_view(viewer_session, binary_id=100, name="Second")
    await viewer_session.commit()
    views = await list_views_by_binary(viewer_session, binary_id=100)
    assert [view.id for view in views] == [first.id, second.id]


@pytest.mark.asyncio
async def test_create_view(viewer_session: AsyncSession) -> None:
    view = await create_view(viewer_session, binary_id=100, name="crash path")
    await viewer_session.commit()
    assert view.name == "crash path"
    assert view.binary_id == 100
    assert (view.camera_x, view.camera_y, view.camera_zoom) == (0.0, 0.0, 1.0)


@pytest.mark.asyncio
async def test_count_views_by_binary(viewer_session: AsyncSession) -> None:
    await _make_view(viewer_session, binary_id=100, name="Default")
    await _make_view(viewer_session, binary_id=100, name="Second")
    await viewer_session.commit()
    assert await count_views_by_binary(viewer_session, binary_id=100) == 2


@pytest.mark.asyncio
async def test_get_view_by_id_eager_loads_nodes(viewer_session: AsyncSession) -> None:
    view = await _make_view(viewer_session, binary_id=100, name="Default")
    await viewer_session.commit()
    fetched = await get_view_by_id(viewer_session, view.id)
    assert fetched is not None and fetched.nodes == []


@pytest.mark.asyncio
async def test_get_view_by_id_returns_none_for_missing(viewer_session: AsyncSession) -> None:
    assert await get_view_by_id(viewer_session, 99999) is None


@pytest.mark.asyncio
async def test_update_view_fields_only_touches_passed_fields(viewer_session: AsyncSession) -> None:
    view = await _make_view(viewer_session, binary_id=100, name="Default")
    await update_view_fields(viewer_session, view, camera_x=10.0)
    await viewer_session.commit()
    assert view.name == "Default"
    assert view.camera_x == 10.0 and view.camera_y == 0.0


@pytest.mark.asyncio
async def test_set_root_function_id_allows_none(viewer_session: AsyncSession) -> None:
    view = await _make_view(viewer_session, binary_id=100, name="Default")
    await set_root_function_id(viewer_session, view, 54321)
    await viewer_session.commit()
    assert view.root_function_id == 54321
    await set_root_function_id(viewer_session, view, None)
    await viewer_session.commit()
    assert view.root_function_id is None


@pytest.mark.asyncio
async def test_delete_view(viewer_session: AsyncSession) -> None:
    view = await _make_view(viewer_session, binary_id=100, name="Default")
    await viewer_session.commit()
    await delete_view(viewer_session, view)
    await viewer_session.commit()
    assert await get_view_by_id(viewer_session, view.id) is None


@pytest.mark.asyncio
async def test_duplicate_view_copies_layout_only(viewer_session: AsyncSession) -> None:
    view = await _make_view(viewer_session, binary_id=100, name="Default")
    await upsert_view_nodes(
        viewer_session,
        view_id=view.id,
        upserts=[
            {
                "function_id": 54321,
                "origin_function_id": 54322,
                "origin_kind": "fanout",
                "pos_x": 5.0,
                "pinned": True,
            }
        ],
    )
    await viewer_session.commit()
    reloaded = await get_view_by_id(viewer_session, view.id)
    assert reloaded is not None
    new_view = await duplicate_view(viewer_session, reloaded)
    await viewer_session.commit()
    assert new_view.id != view.id and new_view.name == "Default (copy)"
    assert len(new_view.nodes) == 1
    assert new_view.nodes[0].function_id == 54321
    assert new_view.nodes[0].pos_x == 5.0 and new_view.nodes[0].pinned is True


@pytest.mark.asyncio
async def test_last_view_preferences_are_viewer_local(viewer_session: AsyncSession) -> None:
    view = await _make_view(viewer_session, binary_id=100, name="Default")
    await set_last_view_id(viewer_session, binary_id=100, view_id=view.id)
    await viewer_session.commit()
    assert await get_last_view_ids(viewer_session, binary_ids=[100]) == {100: view.id}
    await clear_last_view_ids_for_view(viewer_session, view_id=view.id)
    await viewer_session.commit()
    assert await viewer_session.get(BinaryUiState, 100) is None
