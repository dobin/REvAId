"""``GET /events`` (TAD §4.2 endpoint 22, I8 exit criteria).

Note: `httpx.ASGITransport` (used by the `client` fixture) buffers an ASGI
app's entire response body and only returns once the app signals
``more_body=False`` — it cannot represent a genuinely open-ended SSE stream
over HTTP. The live stream generator itself (keepalive timing, event
framing, overflow → reconcile → close) is exercised directly against
`events/bus.py`/`events/sse.py` in `tests/unit/test_event_bus.py`. This file
instead checks the piece `ASGITransport` *can* observe end-to-end: that a
`POST /functions/{id}/summary`/`POST /queue/cancel-pending` call reaches
into the same process-wide `EventBus` instance `GET /events` reads from,
publishing a `queue` event (E5b).
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient

from graphrev.events.bus import InProcessEventBus


async def _get_main_function_id(client: AsyncClient) -> int:
    binaries = (await client.get("/api/v1/binaries")).json()
    acme_id = next(b["id"] for b in binaries if b["name"] == "acme.exe")
    search = (
        await client.get(f"/api/v1/binaries/{acme_id}/functions", params={"q": "main"})
    ).json()
    return int(next(r["id"] for r in search["rows"] if r["displayName"] == "main"))


def _event_bus(client: AsyncClient) -> InProcessEventBus:
    app = client._transport.app  # type: ignore[attr-defined]
    return app.state.event_bus


@pytest.mark.asyncio
async def test_events_stream_starts_with_sse_headers(client: AsyncClient) -> None:
    """Drive the raw ASGI callable directly (bypassing `ASGITransport`, which
    cannot represent an open-ended stream) just long enough to observe the
    `http.response.start` message, then cancel — enough to assert the SSE
    headers without needing the body to ever complete."""
    app = client._transport.app  # type: ignore[attr-defined]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "headers": [],
        "scheme": "http",
        "path": "/api/v1/events",
        "raw_path": b"/api/v1/events",
        "query_string": b"",
        "server": ("test", 80),
        "client": ("test", 0),
        "root_path": "",
    }
    start_message: dict[str, object] = {}
    started = asyncio.Event()

    async def receive() -> dict[str, object]:
        await asyncio.Event().wait()  # never delivers a body; the route doesn't read it
        return {}  # pragma: no cover - unreachable

    async def send(message: dict[str, object]) -> None:
        if message["type"] == "http.response.start":
            start_message.update(message)
            started.set()

    task = asyncio.ensure_future(app(scope, receive, send))
    try:
        await asyncio.wait_for(started.wait(), timeout=5.0)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert start_message["status"] == 200
    headers = dict(start_message["headers"])  # type: ignore[arg-type]
    assert headers[b"content-type"].startswith(b"text/event-stream")
    assert headers[b"cache-control"] == b"no-cache"
    assert headers[b"x-accel-buffering"] == b"no"


@pytest.mark.asyncio
async def test_demanding_a_summary_publishes_a_queue_event(
    client: AsyncClient, ingested: None
) -> None:
    """E5b: a demand call publishes a `queue` event on the process-wide
    `EventBus` — the same bus `GET /events` streams from."""
    function_id = await _get_main_function_id(client)
    bus = _event_bus(client)
    _subscriber_id, queue = bus.subscribe()

    await client.post(f"/api/v1/functions/{function_id}/summary", json={"priority": 0})

    # `demand_summary` now also publishes a `summary` event on the
    # `->pending` transition (see `services/summary_service.py`), ahead of
    # the `queue` event this test cares about — drain past it.
    event = await asyncio.wait_for(queue.get(), timeout=5.0)
    if event.event == "summary":
        event = await asyncio.wait_for(queue.get(), timeout=5.0)
    assert event.event == "queue"
    assert "queuedCount" in event.data or "inFlightCount" in event.data


@pytest.mark.asyncio
async def test_cancel_pending_publishes_a_queue_event(client: AsyncClient, ingested: None) -> None:
    function_id = await _get_main_function_id(client)
    await client.post(f"/api/v1/functions/{function_id}/summary", json={"priority": 3})

    bus = _event_bus(client)
    _subscriber_id, queue = bus.subscribe()

    await client.post("/api/v1/queue/cancel-pending")

    event = await asyncio.wait_for(queue.get(), timeout=5.0)
    assert event.event == "queue"
