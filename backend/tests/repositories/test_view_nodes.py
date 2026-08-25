"""`repositories/view_nodes.py` — batch upsert/remove (TAD §4.3 #12, I6)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Binary, Function, View
from graphrev.repositories.view_nodes import (
    list_nodes_by_view,
    remove_view_nodes,
    upsert_view_nodes,
)


async def _make_binary(session: AsyncSession, *, name: str = "a.exe") -> Binary:
    now = utc_now_iso()
    binary = Binary(name=name, version="1.0", source_path=None, created_at=now, updated_at=now)
    session.add(binary)
    await session.flush()
    return binary


async def _make_view(session: AsyncSession, *, binary_id: int, name: str = "Default") -> View:
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


async def _make_function(session: AsyncSession, *, binary_id: int, address: int) -> Function:
    now = utc_now_iso()
    fn = Function(
        binary_id=binary_id,
        address=address,
        name_ghidra=f"fn_{address:x}",
        created_at=now,
        updated_at=now,
    )
    session.add(fn)
    await session.flush()
    return fn


@pytest.mark.asyncio
async def test_upsert_creates_row_with_defaults_for_omitted_fields(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    view = await _make_view(session, binary_id=binary.id)
    fn = await _make_function(session, binary_id=binary.id, address=0x1000)
    await session.commit()

    await upsert_view_nodes(
        session, view_id=view.id, upserts=[{"function_id": fn.id, "pos_x": 12.0}]
    )
    await session.commit()

    nodes = await list_nodes_by_view(session, view_id=view.id)
    assert len(nodes) == 1
    node = nodes[0]
    assert node.function_id == fn.id
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
    session: AsyncSession,
) -> None:
    binary = await _make_binary(session)
    view = await _make_view(session, binary_id=binary.id)
    fn = await _make_function(session, binary_id=binary.id, address=0x1000)
    await session.commit()

    await upsert_view_nodes(
        session, view_id=view.id, upserts=[{"function_id": fn.id, "pos_x": 1.0, "pinned": False}]
    )
    await session.commit()
    await upsert_view_nodes(
        session, view_id=view.id, upserts=[{"function_id": fn.id, "pos_x": 99.0, "pinned": True}]
    )
    await session.commit()

    nodes = await list_nodes_by_view(session, view_id=view.id)
    assert len(nodes) == 1
    assert nodes[0].pos_x == 99.0
    assert nodes[0].pinned is True


@pytest.mark.asyncio
async def test_upsert_partial_patch_leaves_omitted_fields_untouched(
    session: AsyncSession,
) -> None:
    binary = await _make_binary(session)
    view = await _make_view(session, binary_id=binary.id)
    fn = await _make_function(session, binary_id=binary.id, address=0x1000)
    await session.commit()

    await upsert_view_nodes(
        session, view_id=view.id, upserts=[{"function_id": fn.id, "pos_x": 1.0, "pos_y": 2.0}]
    )
    await session.commit()
    # Only patch pos_x — pos_y must be preserved.
    await upsert_view_nodes(
        session, view_id=view.id, upserts=[{"function_id": fn.id, "pos_x": 5.0}]
    )
    await session.commit()

    nodes = await list_nodes_by_view(session, view_id=view.id)
    assert nodes[0].pos_x == 5.0
    assert nodes[0].pos_y == 2.0


@pytest.mark.asyncio
async def test_remove_is_scoped_to_the_given_view(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    view_a = await _make_view(session, binary_id=binary.id, name="A")
    view_b = await _make_view(session, binary_id=binary.id, name="B")
    fn = await _make_function(session, binary_id=binary.id, address=0x1000)
    await session.commit()

    await upsert_view_nodes(session, view_id=view_a.id, upserts=[{"function_id": fn.id}])
    await upsert_view_nodes(session, view_id=view_b.id, upserts=[{"function_id": fn.id}])
    await session.commit()

    await remove_view_nodes(session, view_id=view_a.id, function_ids=[fn.id])
    await session.commit()

    assert await list_nodes_by_view(session, view_id=view_a.id) == []
    assert len(await list_nodes_by_view(session, view_id=view_b.id)) == 1


@pytest.mark.asyncio
async def test_remove_with_empty_list_is_a_noop(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    view = await _make_view(session, binary_id=binary.id)
    fn = await _make_function(session, binary_id=binary.id, address=0x1000)
    await session.commit()

    await upsert_view_nodes(session, view_id=view.id, upserts=[{"function_id": fn.id}])
    await session.commit()

    await remove_view_nodes(session, view_id=view.id, function_ids=[])
    await session.commit()

    assert len(await list_nodes_by_view(session, view_id=view.id)) == 1
