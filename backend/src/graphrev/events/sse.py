"""SSE wire format + the per-connection generator (TAD §4.2 #22, E5).

``format_sse`` renders one :class:`~graphrev.events.bus.ServerEvent` as the
``id:``/``event:``/``data:`` line group the TAD's payload examples show.
``sse_event_stream`` is the async generator ``api/routers/events.py`` hands
to Starlette's ``StreamingResponse`` — it owns keepalive timing and
subscribe/unsubscribe lifecycle, and is deliberately kept free of any
FastAPI/Starlette import so it can be unit tested as a plain async generator.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from graphrev.events.bus import InProcessEventBus, ServerEvent

#: TAD §2.7 — "a 15s `: keepalive` comment prevents proxy idle timeouts".
_KEEPALIVE_COMMENT = ": keepalive\n\n"


def format_sse(event: ServerEvent) -> str:
    """Render one event as an SSE frame. A monotonic ``id:`` line is always
    present (TAD §2.7 — "so a future replay buffer is additive")."""
    payload = json.dumps(event.data, separators=(",", ":"))
    return f"id: {event.id}\nevent: {event.event}\ndata: {payload}\n\n"


async def sse_event_stream(
    bus: InProcessEventBus, *, keepalive_seconds: float
) -> AsyncIterator[str]:
    """Yield SSE frames for exactly one subscriber, for the lifetime of the
    HTTP connection. Subscribes on entry, always unsubscribes on exit
    (including client disconnect, which surfaces here as
    ``asyncio.CancelledError`` when Starlette tears down the response)."""
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
                # Overflow (bus._force_reconcile_and_close): the reconcile
                # event just yielded above is this subscriber's last one —
                # end the stream so the client's own reconnect logic takes
                # over (TAD §2.7).
                return
    finally:
        bus.unsubscribe(subscriber_id)
