"""Standalone analysis backend ASGI application."""

from __future__ import annotations

from fastapi import FastAPI

from revaid.api.routers import (
    binaries,
    config,
    events,
    functions,
    health,
    internal,
    llm_status,
    queue,
    summaries,
)
from revaid.core.config import Settings, get_settings
from revaid.lifespan import lifespan
from revaid_contracts.app_base import create_base_app
from revaid_contracts.events import InProcessEventBus

__all__ = ["app", "create_app"]


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = create_base_app(
        settings=resolved_settings,
        title="GraphRev Analysis API",
        lifespan_handler=lifespan,
    )
    app.state.event_bus = InProcessEventBus(
        subscriber_queue_size=resolved_settings.sse_subscriber_queue_size
    )
    for router in (
        config.router,
        health.router,
        llm_status.router,
        binaries.router,
        functions.router,
        summaries.router,
        queue.router,
        events.router,
    ):
        app.include_router(router, prefix="/api/v1")
    app.include_router(internal.router)
    return app


app = create_app()
