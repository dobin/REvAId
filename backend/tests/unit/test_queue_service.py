"""Unit tests for `services/queue_service.py`: `InFlightItemDto.started_at`
population (B5) and the shared `queue_event_payload` builder."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Binary, Function
from graphrev.services.queue_service import get_queue_snapshot, queue_event_payload
from graphrev.summarization.queue import SummaryQueue


async def _make_function(session: AsyncSession, *, name: str = "do_thing") -> Function:
    now = utc_now_iso()
    binary = Binary(name="acme.exe", version="1.0", created_at=now, updated_at=now)
    session.add(binary)
    await session.flush()
    fn = Function(
        binary_id=binary.id,
        address=0x1000,
        name_ghidra=name,
        summary_status="pending",
        created_at=now,
        updated_at=now,
    )
    session.add(fn)
    await session.flush()
    await session.commit()
    return fn


async def test_in_flight_item_has_started_at_after_pop(session: AsyncSession) -> None:
    fn = await _make_function(session)
    queue = SummaryQueue(max_depth=10)
    queue.enqueue(fn.id, priority=1)
    await queue.pop()

    snapshot = await get_queue_snapshot(session, queue)
    assert len(snapshot.in_flight) == 1
    assert snapshot.in_flight[0].started_at is not None


async def test_started_at_is_cleared_on_complete(session: AsyncSession) -> None:
    fn = await _make_function(session)
    queue = SummaryQueue(max_depth=10)
    queue.enqueue(fn.id, priority=1)
    await queue.pop()
    queue.complete(fn.id)

    snapshot = await get_queue_snapshot(session, queue)
    assert snapshot.in_flight == []


def test_queue_event_payload_reflects_pause_state() -> None:
    queue = SummaryQueue(max_depth=10)
    assert queue_event_payload(queue)["pausedUntil"] is None

    queue.pause(10.0)
    assert queue_event_payload(queue)["pausedUntil"] is not None
