"""I8 exit criteria for `InProcessEventBus`/`sse_event_stream` (TAD §2.7)."""

from __future__ import annotations

import asyncio

import pytest

from graphrev.events.bus import InProcessEventBus
from graphrev.events.sse import format_sse, sse_event_stream


async def test_publish_delivers_to_all_subscribers() -> None:
    bus = InProcessEventBus(subscriber_queue_size=8)
    _id1, q1 = bus.subscribe()
    _id2, q2 = bus.subscribe()

    bus.publish("summary", {"functionId": 1})

    event1 = await q1.get()
    event2 = await q2.get()
    assert event1.event == "summary"
    assert event1.data == {"functionId": 1}
    assert event2.data == event1.data
    # Distinct monotonic ids, but the SAME event fanned out to both.
    assert event1.id == event2.id


async def test_unsubscribe_stops_delivery() -> None:
    bus = InProcessEventBus(subscriber_queue_size=8)
    subscriber_id, queue = bus.subscribe()
    bus.unsubscribe(subscriber_id)

    bus.publish("summary", {"functionId": 1})

    assert queue.empty()
    assert bus.subscriber_count == 0


async def test_overflow_clears_queue_and_forces_reconcile_then_close() -> None:
    bus = InProcessEventBus(subscriber_queue_size=2)
    subscriber_id, queue = bus.subscribe()

    # Fill the bounded queue, then overflow it.
    bus.publish("summary", {"n": 1})
    bus.publish("summary", {"n": 2})
    bus.publish("summary", {"n": 3})  # triggers overflow handling

    # Overflow handling drains the queue first, so the two "summary" events
    # above are gone; only the reconcile event remains.
    reconcile_event = queue.get_nowait()
    assert reconcile_event.event == "reconcile"
    assert queue.empty()
    assert bus.subscriber_count == 0
    # The SSE generator is expected to call consume_close() right after
    # yielding that reconcile event, and it must report True exactly once.
    assert bus.consume_close(subscriber_id) is True
    assert bus.consume_close(subscriber_id) is False


def test_format_sse_renders_id_event_data_lines() -> None:
    bus = InProcessEventBus(subscriber_queue_size=8)
    bus.publish("summary", {"functionId": 412, "summaryStatus": "ready"})
    _id, queue = bus.subscribe()
    # publish() above happened before this subscribe(), so re-publish to
    # actually land an event in this subscriber's own queue.
    bus.publish("queue", {"inFlightCount": 1})
    event = queue.get_nowait()
    frame = format_sse(event)
    assert frame.startswith(f"id: {event.id}\nevent: queue\ndata: ")
    assert frame.endswith("\n\n")
    assert '"inFlightCount":1' in frame


async def test_sse_event_stream_yields_keepalive_when_idle() -> None:
    bus = InProcessEventBus(subscriber_queue_size=8)
    stream = sse_event_stream(bus, keepalive_seconds=0.05)
    frame = await asyncio.wait_for(anext(stream), timeout=1.0)
    assert frame == ": keepalive\n\n"
    assert bus.subscriber_count == 1
    await stream.aclose()


async def test_sse_event_stream_yields_published_event_before_keepalive() -> None:
    bus = InProcessEventBus(subscriber_queue_size=8)
    stream = sse_event_stream(bus, keepalive_seconds=5.0)
    # Prime the generator up to its first `await` so it has subscribed.
    task = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0)  # let the generator reach `queue.get()`
    bus.publish("summary", {"functionId": 7})
    frame = await asyncio.wait_for(task, timeout=1.0)
    assert "event: summary" in frame
    assert '"functionId":7' in frame
    await stream.aclose()


async def test_sse_event_stream_closes_on_overflow_reconcile() -> None:
    bus = InProcessEventBus(subscriber_queue_size=1)
    stream = sse_event_stream(bus, keepalive_seconds=5.0)
    task = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0)
    bus.publish("summary", {"n": 1})  # fills the size-1 queue
    bus.publish("summary", {"n": 2})  # overflow -> reconcile + close sentinel

    first_frame = await asyncio.wait_for(task, timeout=1.0)
    assert "event: reconcile" in first_frame

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(stream), timeout=1.0)
