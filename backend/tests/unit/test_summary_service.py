"""Unit tests for `services/summary_service.py`'s gap fixes:
pending `summary` SSE events, non-null `pausedUntil` on `queue` events, the
enqueue-before-DB-flip ordering fix, and queue-full -> `QUEUE_FULL`."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.core.errors import AppError, ErrorCode
from graphrev.db.models import Binary, Function
from graphrev.events.bus import InProcessEventBus
from graphrev.services import summary_service
from graphrev.summarization.queue import SummaryQueue


async def _make_function(
    session: AsyncSession, *, name: str = "do_thing", summary_status: str = "none"
) -> Function:
    now = utc_now_iso()
    binary = Binary(name="acme.exe", version="1.0", created_at=now, updated_at=now)
    session.add(binary)
    await session.flush()
    fn = Function(
        binary_id=binary.id,
        address=0x1000,
        name_ghidra=name,
        code_c="int do_thing(void) { return 1; }",
        summary_status=summary_status,
        created_at=now,
        updated_at=now,
    )
    session.add(fn)
    await session.flush()
    await session.commit()
    return fn


async def test_demand_summary_publishes_a_pending_summary_event(session: AsyncSession) -> None:
    fn = await _make_function(session)
    queue = SummaryQueue(max_depth=10)
    bus = InProcessEventBus(subscriber_queue_size=8)
    _sub_id, mailbox = bus.subscribe()

    await summary_service.demand_summary(
        session, queue, function_id=fn.id, priority=1, event_bus=bus
    )

    summary_event = await mailbox.get()
    assert summary_event.event == "summary"
    assert summary_event.data["functionId"] == fn.id
    assert summary_event.data["summaryStatus"] == "pending"

    queue_event = await mailbox.get()
    assert queue_event.event == "queue"


async def test_demand_summary_queue_event_carries_paused_until_when_paused(
    session: AsyncSession,
) -> None:
    fn = await _make_function(session)
    queue = SummaryQueue(max_depth=10)
    queue.pause(30.0)
    bus = InProcessEventBus(subscriber_queue_size=8)
    _sub_id, mailbox = bus.subscribe()

    await summary_service.demand_summary(
        session, queue, function_id=fn.id, priority=1, event_bus=bus
    )

    await mailbox.get()  # summary (pending) event
    queue_event = await mailbox.get()
    assert queue_event.data["pausedUntil"] is not None


async def test_release_summary_demand_queue_event_paused_until_none_when_not_paused(
    session: AsyncSession,
) -> None:
    fn = await _make_function(session)
    queue = SummaryQueue(max_depth=10)
    queue.enqueue(fn.id, priority=2)
    bus = InProcessEventBus(subscriber_queue_size=8)
    _sub_id, mailbox = bus.subscribe()

    summary_service.release_summary_demand(queue, function_id=fn.id, event_bus=bus)

    queue_event = await mailbox.get()
    assert queue_event.data["pausedUntil"] is None


async def test_demand_summary_full_queue_raises_queue_full_and_row_not_stranded_pending(
    session: AsyncSession,
) -> None:
    """B4: the row must NOT be left at `summary_status='pending'` when
    `queue.enqueue` fails — it must still reflect its pre-request status."""
    queue = SummaryQueue(max_depth=1)
    # Fill the queue with one item, then mark it in-flight so eviction has
    # no queued (non-in-flight) candidate to evict, forcing `QueueFullError`.
    queue.enqueue(999999, priority=3)
    await queue.pop()

    fn = await _make_function(session, name="second_fn", summary_status="none")

    with pytest.raises(AppError) as exc_info:
        await summary_service.demand_summary(session, queue, function_id=fn.id, priority=1)
    assert exc_info.value.code == ErrorCode.QUEUE_FULL

    refreshed = (
        await session.execute(select(Function).where(Function.id == fn.id))
    ).scalar_one()
    assert refreshed.summary_status == "none"


async def test_regenerate_summary_full_queue_raises_queue_full_and_row_not_stranded_pending(
    session: AsyncSession,
) -> None:
    queue = SummaryQueue(max_depth=1)
    queue.enqueue(999999, priority=3)
    await queue.pop()

    fn = await _make_function(session, name="second_fn", summary_status="ready")

    with pytest.raises(AppError) as exc_info:
        await summary_service.regenerate_summary(session, queue, function_id=fn.id)
    assert exc_info.value.code == ErrorCode.QUEUE_FULL

    refreshed = (
        await session.execute(select(Function).where(Function.id == fn.id))
    ).scalar_one()
    assert refreshed.summary_status == "ready"
