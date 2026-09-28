"""Standalone viewer UI backend ASGI application."""

from __future__ import annotations

from fastapi import FastAPI

from revaid_ui.api.app_base import create_base_app
from revaid_ui.api.routers import (
    binaries,
    config,
    events,
    functions,
    health,
    llm_status,
    neighbours,
    queue,
    summaries,
    view_nodes,
    views,
)
from revaid_ui.core.config import Settings, get_settings
from revaid_ui.lifespan import lifespan

__all__ = ["app", "create_app"]


def create_app(settings: Settings | None = None) -> FastAPI:
    app = create_base_app(
        settings=settings or get_settings(),
        title="GraphRev Viewer API",
        lifespan_handler=lifespan,
    )
    for router in (
        binaries.router,
        config.router,
        health.router,
        llm_status.router,
        neighbours.router,
        queue.router,
        summaries.router,
        views.router,
        view_nodes.router,
        events.router,
        functions.router,
    ):
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
