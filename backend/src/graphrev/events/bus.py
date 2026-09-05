"""In-process event bus for server→client push (TAD §2.7, E5/E5a/E5b/Q26,
docs/specs/PLAN-I7-I8-I9-I13.md §4.1).

Traffic here is strictly server→client (summary results, queue counts,
binary lifecycle, reconcile hints) — every client→server write stays an
ordinary REST call (TAD §1.3's own rationale for "native `EventSource`, no
library"; see ``docs/adr/0005-sse-transport.md`` for the transport decision).

Each SSE connection owns a bounded ``asyncio.Queue`` (``sse_subscriber_queue_
size``, F1). On overflow — a slow/stuck client that cannot drain fast enough
— the subscriber is NOT silently dropped events (TAD §2.7 explicitly forbids
this: "the client then reconnects and re-reads authoritative
`summary_status`"). Instead its queue is cleared, a single ``reconcile``
event is enqueued, and the connection is closed right after — the client's
own reconnect + reconciliation logic (I8 frontend half) does the rest.

This module is pure in-process pub/sub. It has no DB access and knows
nothing about ``SummaryQueue``/workers — callers (``main.py``'s wiring,
``api/routers/*``) decide what data to publish and when.
"""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ServerEvent:
    """One SSE frame's worth of data — see :func:`graphrev.events.sse.format_sse`
    for the wire rendering (``id:``/``event:``/``data:`` lines, TAD §4.2 #22)."""

    id: int
    event: str  # "summary" | "queue" | "binary" | "llm-status" | "reconcile"
    data: dict[str, object]


class EventBus(Protocol):
    """Publish-side contract. ``main.py`` and the routers depend only on
    this Protocol, not on :class:`InProcessEventBus` directly, so a future
    multi-process deployment could swap the implementation without touching
    call sites (TAD §2.7 sketches exactly this Protocol)."""

    def publish(self, event_type: str, data: dict[str, object]) -> None: ...


@dataclass(slots=True)
class _Subscriber:
    """One live SSE connection's mailbox."""

    queue: asyncio.Queue[ServerEvent] = field(default_factory=lambda: asyncio.Queue())


class InProcessEventBus:
    """The only :class:`EventBus` implementation needed for M0's single
    ASGI process (TAD §1.3 — no multi-process/multi-worker deployment)."""

    def __init__(self, *, subscriber_queue_size: int) -> None:
        self._subscriber_queue_size = subscriber_queue_size
        self._subscribers: dict[int, _Subscriber] = {}
        #: Subscriber ids the SSE generator must close *after* it has
        #: yielded the reconcile event already sitting in that subscriber's
        #: queue (see :meth:`consume_close`). Kept separate from
        #: ``_subscribers`` itself, which is used only for future publishes.
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
        """Register a new SSE connection. Returns an opaque id (for
        :meth:`unsubscribe`/:meth:`consume_close`) and the queue the caller
        should read from."""
        subscriber_id = next(self._next_subscriber_id)
        subscriber = _Subscriber(queue=asyncio.Queue(maxsize=self._subscriber_queue_size))
        self._subscribers[subscriber_id] = subscriber
        return subscriber_id, subscriber.queue

    def unsubscribe(self, subscriber_id: int) -> None:
        self._subscribers.pop(subscriber_id, None)
        self._closing.discard(subscriber_id)

    def consume_close(self, subscriber_id: int) -> bool:
        """Called by :func:`graphrev.events.sse.sse_event_stream` right
        after yielding an event: returns ``True`` exactly once if this
        subscriber was marked for close-after-reconcile (overflow), telling
        the generator to end the stream rather than keep looping."""
        if subscriber_id in self._closing:
            self._closing.discard(subscriber_id)
            return True
        return False

    @property
    def subscriber_count(self) -> int:
        """Exposed for tests only — not part of the :class:`EventBus` Protocol."""
        return len(self._subscribers)

    def _force_reconcile_and_close(self, subscriber_id: int, subscriber: _Subscriber) -> None:
        """Overflow handling (TAD §2.7): drop everything already queued for
        this subscriber and hand it exactly one ``reconcile`` event. The
        subscriber is removed from ``_subscribers`` immediately — a stuck
        client must not keep absorbing future `put_nowait` attempts
        (`QueueFull` on every subsequent publish is pure waste once we've
        already decided to close it) — but ``consume_close`` still reports
        `True` for it once the SSE generator has drained the reconcile
        event, telling that generator to end the stream."""
        while not subscriber.queue.empty():
            try:
                subscriber.queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover - race is harmless
                break
        reconcile_event = ServerEvent(id=next(self._next_event_id), event="reconcile", data={})
        # Safe: the queue was just drained above, and a queue of size >= 1
        # always has room for one item immediately after being emptied.
        subscriber.queue.put_nowait(reconcile_event)
        self._subscribers.pop(subscriber_id, None)
        self._closing.add(subscriber_id)
