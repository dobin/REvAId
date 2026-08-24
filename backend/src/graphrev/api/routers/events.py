"""``GET /events`` — the SSE stream (TAD §4.2 endpoint 22, E5)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from graphrev.events.sse import sse_event_stream

router = APIRouter(tags=["events"])


@router.get("/events")
async def get_events(request: Request) -> StreamingResponse:
    bus = request.app.state.event_bus
    settings = request.app.state.settings
    return StreamingResponse(
        sse_event_stream(bus, keepalive_seconds=settings.sse_keepalive_seconds),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
