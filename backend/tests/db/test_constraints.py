"""Analysis and viewer local constraints, external IDs, and closed enums."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revaid.db.models import Binary, Edge, Function
from revaid_contracts.clock import utc_now_iso
from revaid_ui.db.models import View, ViewNode


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
        name=name,
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
            name="b",
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
async def test_edge_callee_order_is_nullable_and_nonnegative(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    fn_a = await _make_function(session, binary, 0x1000, "a")
    fn_b = await _make_function(session, binary, 0x2000, "b")
    fn_c = await _make_function(session, binary, 0x3000, "c")
    session.add(Edge(binary_id=binary.id, caller_id=fn_a.id, callee_id=fn_b.id, callee_order=None))
    session.add(Edge(binary_id=binary.id, caller_id=fn_a.id, callee_id=fn_c.id, callee_order=0))
    await session.flush()

    session.add(Edge(binary_id=binary.id, caller_id=fn_b.id, callee_id=fn_c.id, callee_order=-1))
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
async def test_view_node_unique_per_view_and_function(viewer_session: AsyncSession) -> None:
    view = View(binary_id=54321, name="Default", created_at=_now(), updated_at=_now())
    viewer_session.add(view)
    await viewer_session.flush()

    viewer_session.add(
        ViewNode(view_id=view.id, function_id=12345, created_at=_now(), updated_at=_now())
    )
    await viewer_session.flush()

    viewer_session.add(
        ViewNode(view_id=view.id, function_id=12345, created_at=_now(), updated_at=_now())
    )
    with pytest.raises(IntegrityError):
        await viewer_session.flush()


@pytest.mark.asyncio
async def test_origin_kind_rejects_garbage(viewer_session: AsyncSession) -> None:
    view = View(binary_id=54321, name="Default", created_at=_now(), updated_at=_now())
    viewer_session.add(view)
    await viewer_session.flush()

    viewer_session.add(
        ViewNode(
            view_id=view.id,
            function_id=12345,
            origin_kind="bogus",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    with pytest.raises(IntegrityError):
        await viewer_session.flush()


@pytest.mark.asyncio
async def test_origin_kind_accepts_fanin(viewer_session: AsyncSession) -> None:
    """0004 widened the CHECK to admit `fanin` (leftward caller fan-out)."""
    view = View(binary_id=54321, name="Default", created_at=_now(), updated_at=_now())
    viewer_session.add(view)
    await viewer_session.flush()

    viewer_session.add(
        ViewNode(
            view_id=view.id,
            function_id=12345,
            origin_function_id=23456,
            origin_kind="fanin",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    # No IntegrityError — the widened CHECK admits it.
    await viewer_session.flush()


@pytest.mark.asyncio
async def test_deleting_binary_cascades_only_analysis_facts(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    fn_a = await _make_function(session, binary, 0x1000, "a")
    fn_b = await _make_function(session, binary, 0x2000, "b")
    session.add(Edge(binary_id=binary.id, caller_id=fn_a.id, callee_id=fn_b.id, kind="call"))
    await session.commit()

    await session.delete(binary)
    await session.commit()

    assert (await session.execute(select(Function))).first() is None
    assert (await session.execute(select(Edge))).first() is None


@pytest.mark.asyncio
async def test_viewer_database_accepts_external_analysis_ids(viewer_session: AsyncSession) -> None:
    view = View(binary_id=98765, name="External", created_at=_now(), updated_at=_now())
    viewer_session.add(view)
    await viewer_session.flush()
    viewer_session.add(
        ViewNode(
            view_id=view.id,
            function_id=87654,
            origin_function_id=76543,
            origin_kind="fanout",
            created_at=_now(),
            updated_at=_now(),
        )
    )
    await viewer_session.flush()


@pytest.mark.asyncio
async def test_deleting_view_cascades_to_local_nodes(viewer_session: AsyncSession) -> None:
    view = View(binary_id=54321, name="Default", created_at=_now(), updated_at=_now())
    viewer_session.add(view)
    await viewer_session.flush()
    node = ViewNode(
        view_id=view.id,
        function_id=12345,
        created_at=_now(),
        updated_at=_now(),
    )
    viewer_session.add(node)
    await viewer_session.commit()

    await viewer_session.delete(view)
    await viewer_session.commit()

    assert (await viewer_session.execute(select(ViewNode))).first() is None


@pytest.mark.asyncio
async def test_external_function_ids_do_not_cascade_in_viewer_db(
    session: AsyncSession, viewer_session: AsyncSession
) -> None:
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
    viewer_session.add(view)
    await viewer_session.flush()
    node = ViewNode(
        view_id=view.id,
        function_id=other.id,
        origin_function_id=fn.id,
        origin_kind="fanout",
        created_at=_now(),
        updated_at=_now(),
    )
    viewer_session.add(node)
    await viewer_session.commit()

    await session.delete(fn)
    await session.commit()

    stored_view = await viewer_session.get(View, view.id)
    stored_node = (await viewer_session.execute(select(ViewNode))).scalar_one()
    assert stored_view is not None and stored_view.root_function_id == fn.id
    assert stored_node.origin_function_id == fn.id
