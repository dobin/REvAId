"""A1/A7/B16: idempotent binary lookup-or-create; I3 list/get/delete."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revaid.core.clock import utc_now_iso
from revaid.db.models import Edge, Function
from revaid.repositories.binaries import (
    delete_binary,
    get_binary_by_id,
    get_or_create_binary,
    list_binaries,
)
from revaid_ui.db.models import BinaryUiState, View, ViewNode
from revaid_ui.repositories.views import get_last_view_ids, set_last_view_id


@pytest.mark.asyncio
async def test_get_or_create_binary_creates_new_row(session: AsyncSession) -> None:
    binary, created = await get_or_create_binary(
        session, name="acme.exe", version="1.0", sha256="a" * 64
    )
    await session.commit()
    assert created is True
    assert binary.name == "acme.exe"
    assert binary.version == "1.0"
    assert binary.sha256 == "a" * 64


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
async def test_get_or_create_binary_refreshes_analysis_image_base(session: AsyncSession) -> None:
    binary, created = await get_or_create_binary(
        session, name="acme.exe", version="1.0", analysis_image_base=0x140000000
    )
    await session.commit()

    refreshed, was_created = await get_or_create_binary(
        session, name="acme.exe", version="1.0", analysis_image_base=0x180000000
    )
    await session.commit()

    assert created is True
    assert was_created is False
    assert refreshed.id == binary.id
    assert refreshed.analysis_image_base == 0x180000000


@pytest.mark.asyncio
async def test_get_or_create_binary_refreshes_sha256(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="legacy.exe", version="1.0")
    await session.commit()

    refreshed, created = await get_or_create_binary(
        session, name="legacy.exe", version="1.0", sha256="b" * 64
    )
    await session.commit()

    assert created is False
    assert refreshed.id == binary.id
    assert refreshed.sha256 == "b" * 64


@pytest.mark.asyncio
async def test_get_or_create_binary_distinguishes_by_version(session: AsyncSession) -> None:
    b1, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    b2, _ = await get_or_create_binary(session, name="acme.exe", version="2.0")
    await session.commit()
    assert b1.id != b2.id


@pytest.mark.asyncio
async def test_last_view_state_is_stored_separately_from_analysis_binary(
    session: AsyncSession,
    viewer_session: AsyncSession,
) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    view = View(
        binary_id=binary.id,
        name="Default",
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
    )
    viewer_session.add(view)
    await viewer_session.commit()

    await set_last_view_id(viewer_session, binary_id=binary.id, view_id=view.id)
    await viewer_session.commit()
    binary2, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await session.commit()
    assert binary2.id == binary.id
    assert await get_last_view_ids(viewer_session, binary_ids=[binary.id]) == {binary.id: view.id}


async def _make_function(session: AsyncSession, *, binary_id: int, address: int) -> Function:
    now = utc_now_iso()
    fn = Function(
        binary_id=binary_id,
        address=address,
        name=f"fn_{address:x}",
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
async def test_delete_binary_cascades_only_analysis_facts(
    session: AsyncSession,
    viewer_session: AsyncSession,
) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    fn1 = await _make_function(session, binary_id=binary.id, address=0x1000)
    fn2 = await _make_function(session, binary_id=binary.id, address=0x1010)
    session.add(Edge(binary_id=binary.id, caller_id=fn1.id, callee_id=fn2.id))
    now = utc_now_iso()
    await session.commit()
    view = View(binary_id=binary.id, name="Default", created_at=now, updated_at=now)
    viewer_session.add(view)
    await viewer_session.flush()
    viewer_session.add(
        ViewNode(
            view_id=view.id,
            function_id=fn1.id,
            created_at=now,
            updated_at=now,
        )
    )
    viewer_session.add(BinaryUiState(binary_id=binary.id, last_view_id=view.id, updated_at=now))
    await viewer_session.commit()
    binary_id = binary.id

    await delete_binary(session, binary)
    await session.commit()

    assert await get_binary_by_id(session, binary_id) is None
    assert (
        await session.execute(select(Function).where(Function.binary_id == binary_id))
    ).first() is None
    assert (await session.execute(select(Edge).where(Edge.binary_id == binary_id))).first() is None
    assert (await viewer_session.execute(select(View).where(View.binary_id == binary_id))).first()
    assert (await viewer_session.execute(select(ViewNode))).first()
