"""Small process-local event bus for viewer invalidations."""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ServerEvent:
    id: int
    event: str
    data: dict[str, object]


@dataclass(slots=True)
class _Subscriber:
    queue: asyncio.Queue[ServerEvent] = field(default_factory=asyncio.Queue)


class InProcessEventBus:
    def __init__(self, *, subscriber_queue_size: int) -> None:
        self._subscriber_queue_size = subscriber_queue_size
        self._subscribers: dict[int, _Subscriber] = {}
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
        subscriber_id = next(self._next_subscriber_id)
        subscriber = _Subscriber(queue=asyncio.Queue(maxsize=self._subscriber_queue_size))
        self._subscribers[subscriber_id] = subscriber
        return subscriber_id, subscriber.queue

    def unsubscribe(self, subscriber_id: int) -> None:
        self._subscribers.pop(subscriber_id, None)
        self._closing.discard(subscriber_id)

    def consume_close(self, subscriber_id: int) -> bool:
        if subscriber_id in self._closing:
            self._closing.discard(subscriber_id)
            return True
        return False

    def _force_reconcile_and_close(self, subscriber_id: int, subscriber: _Subscriber) -> None:
        while not subscriber.queue.empty():
            try:
                subscriber.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        subscriber.queue.put_nowait(
            ServerEvent(id=next(self._next_event_id), event="reconcile", data={})
        )
        self._subscribers.pop(subscriber_id, None)
        self._closing.add(subscriber_id)
