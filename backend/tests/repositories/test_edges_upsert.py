"""B3: edge dedup + self-edges; A7a: fan_in/fan_out/is_utility recompute."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Binary, Edge, Function
from graphrev.repositories.edges import EdgeUpsertValues, upsert_edge, upsert_edges_batch
from graphrev.repositories.functions import (
    recompute_fan_in_fan_out_and_utility,
    upsert_function,
)


async def _make_binary(session: AsyncSession, name: str = "acme.exe") -> Binary:
    now = utc_now_iso()
    binary = Binary(name=name, version="1.0", created_at=now, updated_at=now)
    session.add(binary)
    await session.flush()
    return binary


@pytest.mark.asyncio
async def test_upsert_edge_duplicate_pair_refreshes_non_null_order(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    a_id, _ = await upsert_function(session, binary_id=binary.id, address=0x1, name_ghidra="a")
    b_id, _ = await upsert_function(session, binary_id=binary.id, address=0x2, name_ghidra="b")
    await session.commit()

    inserted1 = await upsert_edge(
        session, binary_id=binary.id, caller_id=a_id, callee_id=b_id, callee_order=0
    )
    await session.commit()
    inserted2 = await upsert_edge(
        session, binary_id=binary.id, caller_id=a_id, callee_id=b_id, callee_order=4
    )
    await session.commit()

    assert inserted1 is True
    assert inserted2 is False
    edge = (
        await session.execute(select(Edge).where(Edge.caller_id == a_id, Edge.callee_id == b_id))
    ).scalar_one()
    assert edge.callee_order == 4


@pytest.mark.asyncio
async def test_upsert_edge_legacy_order_does_not_clear_known_order(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    a_id, _ = await upsert_function(session, binary_id=binary.id, address=0x1, name_ghidra="a")
    b_id, _ = await upsert_function(session, binary_id=binary.id, address=0x2, name_ghidra="b")
    await upsert_edge(session, binary_id=binary.id, caller_id=a_id, callee_id=b_id, callee_order=3)
    await session.commit()

    inserted = await upsert_edge(session, binary_id=binary.id, caller_id=a_id, callee_id=b_id)
    await session.commit()

    assert inserted is False
    edge = (
        await session.execute(select(Edge).where(Edge.caller_id == a_id, Edge.callee_id == b_id))
    ).scalar_one()
    assert edge.callee_order == 3


@pytest.mark.asyncio
async def test_upsert_edge_allows_self_edge(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    a_id, _ = await upsert_function(session, binary_id=binary.id, address=0x1, name_ghidra="a")
    await session.commit()

    inserted = await upsert_edge(session, binary_id=binary.id, caller_id=a_id, callee_id=a_id)
    await session.commit()

    assert inserted is True


@pytest.mark.asyncio
async def test_batch_upsert_edges_deduplicates_input_and_existing_rows(
    session: AsyncSession,
) -> None:
    binary = await _make_binary(session)
    a_id, _ = await upsert_function(session, binary_id=binary.id, address=0x1, name_ghidra="a")
    b_id, _ = await upsert_function(session, binary_id=binary.id, address=0x2, name_ghidra="b")
    c_id, _ = await upsert_function(session, binary_id=binary.id, address=0x3, name_ghidra="c")
    await session.commit()

    inserted, skipped = await upsert_edges_batch(
        session,
        binary_id=binary.id,
        edges=[
            EdgeUpsertValues(a_id, b_id, 0),
            EdgeUpsertValues(a_id, b_id, 0),
            EdgeUpsertValues(b_id, c_id, 0),
        ],
    )
    await session.commit()
    assert inserted == 2
    assert skipped == 1

    inserted, skipped = await upsert_edges_batch(
        session,
        binary_id=binary.id,
        edges=[EdgeUpsertValues(a_id, b_id, 2), EdgeUpsertValues(b_id, c_id)],
    )
    assert inserted == 0
    assert skipped == 2
    assert (
        await session.execute(select(Edge.callee_order).where(Edge.caller_id == a_id))
    ).scalar_one() == 2


@pytest.mark.asyncio
async def test_recompute_fan_in_fan_out_and_utility(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    hub_id, _ = await upsert_function(session, binary_id=binary.id, address=0x1, name_ghidra="hub")
    caller_ids = []
    for i in range(3):
        cid, _ = await upsert_function(
            session, binary_id=binary.id, address=0x100 + i, name_ghidra=f"caller{i}"
        )
        caller_ids.append(cid)
    await session.commit()

    for cid in caller_ids:
        await upsert_edge(session, binary_id=binary.id, caller_id=cid, callee_id=hub_id)
    await session.commit()

    await recompute_fan_in_fan_out_and_utility(session, binary_id=binary.id, threshold=2)
    await session.commit()

    hub = await session.get(Function, hub_id)
    assert hub is not None
    assert hub.fan_in == 3
    assert hub.is_utility is True  # 3 > 2

    caller0 = await session.get(Function, caller_ids[0])
    assert caller0 is not None
    assert caller0.fan_out == 1
    assert caller0.fan_in == 0
    assert caller0.is_utility is False  # 0 > 2 is False


@pytest.mark.asyncio
async def test_recompute_is_scoped_to_one_binary(session: AsyncSession) -> None:
    binary_a = await _make_binary(session, "acme.exe")
    binary_b = await _make_binary(session, "libparse.dll")

    hub_a_id, _ = await upsert_function(
        session, binary_id=binary_a.id, address=0x1, name_ghidra="hub_a"
    )
    hub_b_id, _ = await upsert_function(
        session, binary_id=binary_b.id, address=0x1, name_ghidra="hub_b"
    )
    caller_a_id, _ = await upsert_function(
        session, binary_id=binary_a.id, address=0x2, name_ghidra="caller_a"
    )
    await session.commit()

    await upsert_edge(session, binary_id=binary_a.id, caller_id=caller_a_id, callee_id=hub_a_id)
    await session.commit()

    await recompute_fan_in_fan_out_and_utility(session, binary_id=binary_a.id, threshold=0)
    await session.commit()

    hub_a = await session.get(Function, hub_a_id)
    hub_b = await session.get(Function, hub_b_id)
    assert hub_a is not None
    assert hub_b is not None
    assert hub_a.fan_in == 1
    # binary_b's hub was never touched by the binary_a-scoped recompute.
    assert hub_b.fan_in == 0
