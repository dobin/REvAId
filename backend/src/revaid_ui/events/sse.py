"""SSE rendering and keepalive generator for the viewer event stream."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from revaid_ui.events.bus import InProcessEventBus, ServerEvent

_KEEPALIVE_COMMENT = ": keepalive\n\n"


def format_sse(event: ServerEvent) -> str:
    payload = json.dumps(event.data, separators=(",", ":"))
    return f"id: {event.id}\nevent: {event.event}\ndata: {payload}\n\n"


async def sse_event_stream(
    bus: InProcessEventBus, *, keepalive_seconds: float
) -> AsyncIterator[str]:
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
                return
    finally:
        bus.unsubscribe(subscriber_id)
