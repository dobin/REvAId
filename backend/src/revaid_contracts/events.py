"""In-process event bus and SSE rendering shared by the analysis and viewer services.

Traffic is strictly server→client (TAD §2.7, E5): every client→server write stays
an ordinary REST call. Each SSE connection owns a bounded ``asyncio.Queue``. On
overflow the subscriber's queue is cleared, a single ``reconcile`` event is
enqueued, and the connection is closed right after, so the client reconnects and
re-reads authoritative state instead of silently missing events.

This module is pure in-process pub/sub with no DB access.
"""

from __future__ import annotations

import asyncio
import itertools
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

__all__ = [
    "EventBus",
    "InProcessEventBus",
    "ServerEvent",
    "format_sse",
    "sse_event_stream",
]

#: TAD §2.7 — "a 15s `: keepalive` comment prevents proxy idle timeouts".
_KEEPALIVE_COMMENT = ": keepalive\n\n"


@dataclass(frozen=True, slots=True)
class ServerEvent:
    """One SSE frame's worth of data; see :func:`format_sse` for the wire form."""

    id: int
    event: str  # "summary" | "queue" | "binary" | "llm-status" | "reconcile"
    data: dict[str, object]


class EventBus(Protocol):
    """Publish-side contract; callers depend on this, not on the implementation."""

    def publish(self, event_type: str, data: dict[str, object]) -> None: ...


@dataclass(slots=True)
class _Subscriber:
    """One live SSE connection's mailbox."""

    queue: asyncio.Queue[ServerEvent] = field(default_factory=lambda: asyncio.Queue())


class InProcessEventBus:
    """Process-local :class:`EventBus` (single ASGI process, TAD §1.3)."""

    def __init__(self, *, subscriber_queue_size: int) -> None:
        self._subscriber_queue_size = subscriber_queue_size
        self._subscribers: dict[int, _Subscriber] = {}
        #: Subscriber ids the SSE generator must close *after* it has yielded
        #: the reconcile event already sitting in that subscriber's queue.
        self._closing: set[int] = set()
        self._next_subscriber_id = itertools.count(1)
        self._next_event_id = itertools.count(1)

    def publish(self, event_type: str, data: dict[str, object]) -> None:
        event = ServerEvent(id=next(self._next_event_id), event=event_type, data=data)
        for subscriber_id, subscriber in list(self._subscribers.items()):
            try:
                subscriber.queue.put_nowait(event)
            except asyncio.QueueFull:
                self._force_reconcile_and_close(subscriber_id, subscriber)

    def subscribe(self) -> tuple[int, asyncio.Queue[ServerEvent]]:
        """Register a new SSE connection; returns an opaque id and its queue."""
        subscriber_id = next(self._next_subscriber_id)
        subscriber = _Subscriber(queue=asyncio.Queue(maxsize=self._subscriber_queue_size))
        self._subscribers[subscriber_id] = subscriber
        return subscriber_id, subscriber.queue

    def unsubscribe(self, subscriber_id: int) -> None:
        self._subscribers.pop(subscriber_id, None)
        self._closing.discard(subscriber_id)

    def consume_close(self, subscriber_id: int) -> bool:
        """Return ``True`` exactly once if the subscriber was marked to close (overflow)."""
        if subscriber_id in self._closing:
            self._closing.discard(subscriber_id)
            return True
        return False

    @property
    def subscriber_count(self) -> int:
        """Exposed for tests only — not part of the :class:`EventBus` Protocol."""
        return len(self._subscribers)

    def _force_reconcile_and_close(self, subscriber_id: int, subscriber: _Subscriber) -> None:
        """Drop queued events, hand the subscriber one ``reconcile``, and mark it closing."""
        while not subscriber.queue.empty():
            try:
                subscriber.queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover - race is harmless
                break
        reconcile_event = ServerEvent(id=next(self._next_event_id), event="reconcile", data={})
        # Safe: the queue was just drained, so it has room for one item.
        subscriber.queue.put_nowait(reconcile_event)
        self._subscribers.pop(subscriber_id, None)
        self._closing.add(subscriber_id)


def format_sse(event: ServerEvent) -> str:
    """Render one event as an SSE frame; a monotonic ``id:`` line is always present."""
    payload = json.dumps(event.data, separators=(",", ":"))
    return f"id: {event.id}\nevent: {event.event}\ndata: {payload}\n\n"


async def sse_event_stream(
    bus: InProcessEventBus, *, keepalive_seconds: float
) -> AsyncIterator[str]:
    """Yield SSE frames for exactly one subscriber for the life of the connection."""
    subscriber_id, queue = bus.subscribe()
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=keepalive_seconds)
            except TimeoutError:
                yield _KEEPALIVE_COMMENT
                continue
            yield format_sse(event)
            if bus.consume_close(subscriber_id):
                # Overflow: the reconcile event just yielded was this subscriber's last.
                return
    finally:
        bus.unsubscribe(subscriber_id)
