"""Lifecycle for the standalone viewer service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from time import monotonic

from fastapi import FastAPI

from revaid_contracts.analysis import AnalysisClient
from revaid_contracts.logging import configure_logging, get_logger
from revaid_ui.analysis.client import HttpAnalysisClient
from revaid_ui.core.config import Settings
from revaid_ui.db.engine import create_engine, create_session_factory, dispose_engine
from revaid_ui.db.revision import VIEWER_MIGRATION_REVISION, read_revision, require_revision
from revaid_ui.db.startup import reconcile_viewer_state
from revaid_ui.events.bus import InProcessEventBus

logger = get_logger(__name__)


async def wait_for_analysis(
    analysis: AnalysisClient,
    *,
    timeout_seconds: float = 30.0,
    retry_interval_seconds: float = 0.25,
) -> None:
    """Wait briefly for analysis readiness before reconciling saved viewer state."""
    deadline = monotonic() + timeout_seconds
    last_error: Exception | None = None
    while True:
        try:
            if await analysis.health():
                return
            last_error = RuntimeError("Analysis service health check is not ready.")
        except Exception as exc:  # temporary connection failures during parallel startup
            last_error = exc
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise RuntimeError(
                f"Analysis service did not become ready within {timeout_seconds:g} seconds."
            ) from last_error
        await asyncio.sleep(min(retry_interval_seconds, remaining))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings)
    viewer_engine = create_engine(settings, db_path=settings.viewer_db_path)
    viewer_session_factory = create_session_factory(viewer_engine)
    app.state.viewer_engine = viewer_engine
    app.state.viewer_session_factory = viewer_session_factory
    app.state.event_bus = InProcessEventBus(
        subscriber_queue_size=settings.sse_subscriber_queue_size
    )
    existing_analysis_client = getattr(app.state, "analysis_client", None)
    analysis_client = existing_analysis_client or HttpAnalysisClient(
        settings.analysis_internal_url,
        timeout_seconds=settings.analysis_request_timeout_seconds,
        max_response_bytes=settings.analysis_max_response_bytes,
        token=settings.analysis_internal_token,
    )
    app.state.analysis_client = analysis_client
    reconcile_task: asyncio.Task[None] | None = None
    try:
        revision = await read_revision(viewer_session_factory, "Viewer")
        require_revision(revision, VIEWER_MIGRATION_REVISION, "Viewer")
        await wait_for_analysis(analysis_client)
        async with viewer_session_factory() as viewer_session:
            await reconcile_viewer_state(analysis_client, viewer_session)
        reconcile_task = asyncio.create_task(
            viewer_reconcile_loop(app, interval_seconds=settings.sse_keepalive_seconds)
        )
        yield
    finally:
        if reconcile_task is not None:
            reconcile_task.cancel()
            with suppress(asyncio.CancelledError):
                await reconcile_task
        if existing_analysis_client is None:
            await analysis_client.aclose()
        await dispose_engine(viewer_engine)


async def viewer_reconcile_loop(app: FastAPI, *, interval_seconds: float) -> None:
    """Publish invalidations while analysis-backend events remain process-local."""
    while True:
        await asyncio.sleep(max(interval_seconds, 1.0))
        app.state.event_bus.publish("reconcile", {})
