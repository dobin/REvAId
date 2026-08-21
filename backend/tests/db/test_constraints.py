"""B2/B3 uniqueness, self-edges, cascades, SET NULLs, and closed-enum CHECKs."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Binary, Edge, Function, View, ViewNode


def _now() -> str:
    return utc_now_iso()


async def _make_binary(session: AsyncSession, name: str = "acme.exe") -> Binary:
    binary = Binary(name=name, version="1.0", created_at=_now(), updated_at=_now())
    session.add(binary)
    await session.flush()
    return binary


async def _make_function(
    session: AsyncSession, binary: Binary, address: int, name: str
) -> Function:
    fn = Function(
        binary_id=binary.id,
        address=address,
        name_ghidra=name,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(fn)
    await session.flush()
    return fn


@pytest.mark.asyncio
async def test_binary_address_unique(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    await _make_function(session, binary, address=0x1000, name="a")
    session.add(
        Function(
            binary_id=binary.id,
            address=0x1000,
            name_ghidra="b",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_edge_pair_unique_but_self_edge_allowed(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    fn_a = await _make_function(session, binary, 0x1000, "a")
    fn_b = await _make_function(session, binary, 0x2000, "b")

    session.add(Edge(binary_id=binary.id, caller_id=fn_a.id, callee_id=fn_b.id, kind="call"))
    await session.flush()

    # Self-edge (recursion) must be allowed (B3).
    session.add(Edge(binary_id=binary.id, caller_id=fn_a.id, callee_id=fn_a.id, kind="call"))
    await session.flush()

    # Duplicate pair must be rejected.
    session.add(Edge(binary_id=binary.id, caller_id=fn_a.id, callee_id=fn_b.id, kind="call"))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_edge_kind_rejects_non_call_value(session: AsyncSession) -> None:
    """D-3: edges.kind is narrowed to ('call') in 0001_initial."""
    binary = await _make_binary(session)
    fn_a = await _make_function(session, binary, 0x1000, "a")
    fn_b = await _make_function(session, binary, 0x2000, "b")
    session.add(Edge(binary_id=binary.id, caller_id=fn_a.id, callee_id=fn_b.id, kind="data_xref"))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_summary_status_accepts_stale(session: AsyncSession) -> None:
    """D-4: summary_status keeps all five values including 'stale'."""
    binary = await _make_binary(session)
    fn = await _make_function(session, binary, 0x1000, "a")
    fn.summary_status = "stale"
    await session.flush()


@pytest.mark.asyncio
async def test_summary_status_rejects_garbage(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    fn = await _make_function(session, binary, 0x1000, "a")
    fn.summary_status = "bogus"
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_view_node_unique_per_view_and_function(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    fn = await _make_function(session, binary, 0x1000, "a")
    view = View(binary_id=binary.id, name="Default", created_at=_now(), updated_at=_now())
    session.add(view)
    await session.flush()

    session.add(ViewNode(view_id=view.id, function_id=fn.id, created_at=_now(), updated_at=_now()))
    await session.flush()

    session.add(ViewNode(view_id=view.id, function_id=fn.id, created_at=_now(), updated_at=_now()))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_origin_kind_rejects_garbage(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    fn = await _make_function(session, binary, 0x1000, "a")
    view = View(binary_id=binary.id, name="Default", created_at=_now(), updated_at=_now())
    session.add(view)
    await session.flush()

    session.add(
        ViewNode(
            view_id=view.id,
            function_id=fn.id,
            origin_kind="bogus",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_deleting_binary_cascades_to_children(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    fn_a = await _make_function(session, binary, 0x1000, "a")
    fn_b = await _make_function(session, binary, 0x2000, "b")
    session.add(Edge(binary_id=binary.id, caller_id=fn_a.id, callee_id=fn_b.id, kind="call"))
    view = View(binary_id=binary.id, name="Default", created_at=_now(), updated_at=_now())
    session.add(view)
    await session.flush()
    session.add(
        ViewNode(view_id=view.id, function_id=fn_a.id, created_at=_now(), updated_at=_now())
    )
    await session.commit()

    await session.delete(binary)
    await session.commit()

    assert (await session.execute(select(Function))).first() is None
    assert (await session.execute(select(Edge))).first() is None
    assert (await session.execute(select(View))).first() is None
    assert (await session.execute(select(ViewNode))).first() is None


@pytest.mark.asyncio
async def test_deleting_view_nulls_binary_last_view_id(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    view = View(binary_id=binary.id, name="Default", created_at=_now(), updated_at=_now())
    session.add(view)
    await session.flush()
    binary.last_view_id = view.id
    await session.commit()

    await session.delete(view)
    await session.commit()

    await session.refresh(binary)
    assert binary.last_view_id is None


@pytest.mark.asyncio
async def test_deleting_function_nulls_root_and_origin_references(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    fn = await _make_function(session, binary, 0x1000, "a")
    other = await _make_function(session, binary, 0x2000, "b")
    view = View(
        binary_id=binary.id,
        name="Default",
        root_function_id=fn.id,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(view)
    await session.flush()
    session.add(
        ViewNode(
            view_id=view.id,
            function_id=other.id,
            origin_function_id=fn.id,
            origin_kind="fanout",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    await session.commit()

    await session.delete(fn)
    await session.commit()

    await session.refresh(view)
    assert view.root_function_id is None

    node = (await session.execute(select(ViewNode))).scalar_one()
    assert node.origin_function_id is None
