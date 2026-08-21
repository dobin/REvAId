"""`repositories/views.py::list_views_by_binary` — read-only listing."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Binary, View
from graphrev.repositories.views import list_views_by_binary


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
