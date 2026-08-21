"""A1/A7/B16: idempotent binary lookup-or-create; I3 list/get/delete."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Edge, Function, View, ViewNode
from graphrev.repositories.binaries import (
    delete_binary,
    get_binary_by_id,
    get_or_create_binary,
    list_binaries,
)


@pytest.mark.asyncio
async def test_get_or_create_binary_creates_new_row(session: AsyncSession) -> None:
    binary, created = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await session.commit()
    assert created is True
    assert binary.name == "acme.exe"
    assert binary.version == "1.0"


@pytest.mark.asyncio
async def test_get_or_create_binary_is_idempotent(session: AsyncSession) -> None:
    binary1, created1 = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await session.commit()
    binary2, created2 = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await session.commit()

    assert binary1.id == binary2.id
    assert created1 is True
    assert created2 is False


@pytest.mark.asyncio
async def test_get_or_create_binary_distinguishes_by_version(session: AsyncSession) -> None:
    b1, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    b2, _ = await get_or_create_binary(session, name="acme.exe", version="2.0")
    await session.commit()
    assert b1.id != b2.id


@pytest.mark.asyncio
async def test_get_or_create_binary_never_touches_last_view_id(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await session.commit()
    assert binary.last_view_id is None

    binary2, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await session.commit()
    assert binary2.last_view_id is None


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
async def test_list_binaries_returns_function_and_edge_counts(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    fn1 = await _make_function(session, binary_id=binary.id, address=0x1000)
    fn2 = await _make_function(session, binary_id=binary.id, address=0x1010)
    session.add(Edge(binary_id=binary.id, caller_id=fn1.id, callee_id=fn2.id))
    await session.commit()

    rows = await list_binaries(session)
    assert len(rows) == 1
    assert rows[0].binary.id == binary.id
    assert rows[0].function_count == 2
    assert rows[0].edge_count == 1


@pytest.mark.asyncio
async def test_list_binaries_empty_binary_has_zero_counts(session: AsyncSession) -> None:
    await get_or_create_binary(session, name="empty.exe", version="1.0")
    await session.commit()

    rows = await list_binaries(session)
    assert len(rows) == 1
    assert rows[0].function_count == 0
    assert rows[0].edge_count == 0


@pytest.mark.asyncio
async def test_get_binary_by_id_returns_none_when_missing(session: AsyncSession) -> None:
    assert await get_binary_by_id(session, 999) is None


@pytest.mark.asyncio
async def test_get_binary_by_id_returns_the_row(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await session.commit()
    fetched = await get_binary_by_id(session, binary.id)
    assert fetched is not None
    assert fetched.id == binary.id


@pytest.mark.asyncio
async def test_delete_binary_cascades_functions_edges_views_and_view_nodes(
    session: AsyncSession,
) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    fn1 = await _make_function(session, binary_id=binary.id, address=0x1000)
    fn2 = await _make_function(session, binary_id=binary.id, address=0x1010)
    session.add(Edge(binary_id=binary.id, caller_id=fn1.id, callee_id=fn2.id))
    now = utc_now_iso()
    view = View(binary_id=binary.id, name="Default", created_at=now, updated_at=now)
    session.add(view)
    await session.flush()
    session.add(
        ViewNode(
            view_id=view.id,
            function_id=fn1.id,
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()
    binary_id = binary.id

    await delete_binary(session, binary)
    await session.commit()

    assert await get_binary_by_id(session, binary_id) is None
    assert (
        await session.execute(select(Function).where(Function.binary_id == binary_id))
    ).first() is None
    assert (await session.execute(select(Edge).where(Edge.binary_id == binary_id))).first() is None
    assert (await session.execute(select(View).where(View.binary_id == binary_id))).first() is None
    assert (await session.execute(select(ViewNode))).first() is None
