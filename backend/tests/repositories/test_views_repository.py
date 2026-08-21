"""`repositories/views.py` — listing + full CRUD (TAD §4.2 #9-#11, I6)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Binary, Function, View
from graphrev.repositories.view_nodes import upsert_view_nodes
from graphrev.repositories.views import (
    count_views_by_binary,
    create_view,
    delete_view,
    duplicate_view,
    get_view_by_id,
    list_views_by_binary,
    set_root_function_id,
    update_view_fields,
)


async def _make_binary(session: AsyncSession, *, name: str) -> Binary:
    now = utc_now_iso()
    binary = Binary(name=name, version="1.0", source_path=None, created_at=now, updated_at=now)
    session.add(binary)
    await session.flush()
    return binary


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
    session: AsyncSession,
) -> None:
    binary_a = await _make_binary(session, name="a.exe")
    binary_b = await _make_binary(session, name="b.exe")
    await _make_view(session, binary_id=binary_a.id, name="Default")
    await _make_view(session, binary_id=binary_b.id, name="Default")
    await session.commit()

    views = await list_views_by_binary(session, binary_id=binary_a.id)
    assert len(views) == 1
    assert views[0].binary_id == binary_a.id


@pytest.mark.asyncio
async def test_list_views_by_binary_empty_for_binary_with_no_views(
    session: AsyncSession,
) -> None:
    binary = await _make_binary(session, name="a.exe")
    await session.commit()

    views = await list_views_by_binary(session, binary_id=binary.id)
    assert views == []


@pytest.mark.asyncio
async def test_list_views_by_binary_orders_by_id(session: AsyncSession) -> None:
    binary = await _make_binary(session, name="a.exe")
    first = await _make_view(session, binary_id=binary.id, name="First")
    second = await _make_view(session, binary_id=binary.id, name="Second")
    await session.commit()

    views = await list_views_by_binary(session, binary_id=binary.id)
    assert [v.id for v in views] == [first.id, second.id]


@pytest.mark.asyncio
async def test_create_view(session: AsyncSession) -> None:
    binary = await _make_binary(session, name="a.exe")
    await session.commit()

    view = await create_view(session, binary_id=binary.id, name="crash path")
    await session.commit()

    assert view.id is not None
    assert view.name == "crash path"
    assert view.binary_id == binary.id
    assert view.camera_x == 0.0 and view.camera_y == 0.0 and view.camera_zoom == 1.0


@pytest.mark.asyncio
async def test_count_views_by_binary(session: AsyncSession) -> None:
    binary = await _make_binary(session, name="a.exe")
    await _make_view(session, binary_id=binary.id, name="Default")
    await _make_view(session, binary_id=binary.id, name="Second")
    await session.commit()

    assert await count_views_by_binary(session, binary_id=binary.id) == 2


@pytest.mark.asyncio
async def test_get_view_by_id_eager_loads_nodes(session: AsyncSession) -> None:
    binary = await _make_binary(session, name="a.exe")
    view = await _make_view(session, binary_id=binary.id, name="Default")
    await session.commit()

    fetched = await get_view_by_id(session, view.id)
    assert fetched is not None
    assert fetched.nodes == []


@pytest.mark.asyncio
async def test_get_view_by_id_returns_none_for_missing(session: AsyncSession) -> None:
    assert await get_view_by_id(session, 99999) is None


@pytest.mark.asyncio
async def test_update_view_fields_only_touches_passed_fields(session: AsyncSession) -> None:
    binary = await _make_binary(session, name="a.exe")
    view = await _make_view(session, binary_id=binary.id, name="Default")
    await session.commit()

    await update_view_fields(session, view, camera_x=10.0)
    await session.commit()

    assert view.name == "Default"
    assert view.camera_x == 10.0
    assert view.camera_y == 0.0


@pytest.mark.asyncio
async def test_set_root_function_id_allows_none(session: AsyncSession) -> None:
    binary = await _make_binary(session, name="a.exe")
    view = await _make_view(session, binary_id=binary.id, name="Default")
    now = utc_now_iso()
    fn = Function(
        binary_id=binary.id, address=0x1000, name_ghidra="fn_1000", created_at=now, updated_at=now
    )
    session.add(fn)
    await session.flush()
    await session.commit()

    await set_root_function_id(session, view, fn.id)
    await session.commit()
    assert view.root_function_id == fn.id

    await set_root_function_id(session, view, None)
    await session.commit()
    assert view.root_function_id is None


@pytest.mark.asyncio
async def test_delete_view(session: AsyncSession) -> None:
    binary = await _make_binary(session, name="a.exe")
    view = await _make_view(session, binary_id=binary.id, name="Default")
    await session.commit()

    await delete_view(session, view)
    await session.commit()

    assert await get_view_by_id(session, view.id) is None


@pytest.mark.asyncio
async def test_duplicate_view_copies_layout_only(session: AsyncSession) -> None:
    binary = await _make_binary(session, name="a.exe")
    view = await _make_view(session, binary_id=binary.id, name="Default")
    now = utc_now_iso()
    fn = Function(
        binary_id=binary.id, address=0x1000, name_ghidra="fn_1000", created_at=now, updated_at=now
    )
    session.add(fn)
    await session.flush()
    await session.commit()

    await upsert_view_nodes(
        session, view_id=view.id, upserts=[{"function_id": fn.id, "pos_x": 5.0, "pinned": True}]
    )
    await session.commit()

    reloaded = await get_view_by_id(session, view.id)
    assert reloaded is not None
    new_view = await duplicate_view(session, reloaded)
    await session.commit()

    assert new_view.id != view.id
    assert new_view.name == "Default (copy)"
    assert len(new_view.nodes) == 1
    assert new_view.nodes[0].function_id == fn.id
    assert new_view.nodes[0].pos_x == 5.0
    assert new_view.nodes[0].pinned is True
