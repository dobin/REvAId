"""FastAPI application factory + lifespan (TAD §2.1, §2.2).

The lifespan asserts the DB is already at ``head`` (fail loudly rather than
silently creating tables — Alembic is the only way this schema is created,
docs/adr/0002), then runs the two startup hooks (C5b restart recovery, F1b
threshold recompute) before the app starts serving traffic.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from graphrev.adapters.llm import create_adapter as create_llm_adapter
from graphrev.api.routers import binaries as binaries_router
from graphrev.api.routers import config as config_router
from graphrev.api.routers import events as events_router
from graphrev.api.routers import functions as functions_router
from graphrev.api.routers import health as health_router
from graphrev.api.routers import neighbours as neighbours_router
from graphrev.api.routers import queue as queue_router
from graphrev.api.routers import summaries as summaries_router
from graphrev.api.routers import view_nodes as view_nodes_router
from graphrev.api.routers import views as views_router
from graphrev.core.config import Settings, get_settings
from graphrev.core.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from graphrev.core.logging import (
    bind_request_id,
    clear_request_context,
    configure_logging,
    get_logger,
)
from graphrev.db.engine import create_engine, create_session_factory, dispose_engine
from graphrev.db.startup import recompute_utility_if_threshold_changed, recover_pending_summaries
from graphrev.events.bus import InProcessEventBus
from graphrev.summarization.queue import SummaryQueue
from graphrev.summarization.worker import SummaryWorkerPool

logger = get_logger(__name__)


class MigrationNotAppliedError(RuntimeError):
    """Raised when the DB has no `alembic_version` row at startup.

    The fix is always `just migrate` / `alembic upgrade head` — this app never
    creates tables itself.
    """


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    async with session_factory() as session:
        try:
            result = await session.execute(text("SELECT version_num FROM alembic_version"))
            revision = result.scalar_one_or_none()
        except Exception as exc:
            raise MigrationNotAppliedError(
                "Database has not been migrated. Run `just migrate` "
                "(or `uv run alembic upgrade head` in backend/) before starting the API."
            ) from exc

        if revision is None:
            raise MigrationNotAppliedError(
                "Database has no applied migration. Run `just migrate` first."
            )

        # C5b: no function may display "Analyzing..." with no worker behind
        # it. Must run BEFORE the worker pool starts, or an orphaned
        # `pending` row from the recovery scan itself could race with a
        # fresh worker starting to process it.
        await recover_pending_summaries(session)
        await recompute_utility_if_threshold_changed(session, settings)

    # I8: the event bus. Constructed before the worker pool so the pool's
    # `result_listener` can publish `summary` events (E5a) the moment a
    # worker persists a result — every SSE subscriber sees it in-flight.
    event_bus = InProcessEventBus(subscriber_queue_size=settings.sse_subscriber_queue_size)
    app.state.event_bus = event_bus

    async def _publish_summary_event(
        *,
        function_id: int,
        binary_id: int,  # noqa: ARG001 - not part of the E5a payload; kept for future use
        summary_status: str,
        summary_short: str | None,
        summary_model: str | None,
        low_confidence: bool,
        generated_at: str | None,
        error_code: str | None,
        name_llm: str | None = None,
    ) -> None:
        event_bus.publish(
            "summary",
            {
                "functionId": function_id,
                "summaryStatus": summary_status,
                "summaryShort": summary_short,
                "summaryModel": summary_model,
                "lowConfidence": low_confidence,
                "generatedAt": generated_at,
                "errorCode": error_code,
                # C13 auto-display: the LLM-proposed name, so the UI can patch
                # `displayName`/`nameLlm` on every surface without a refetch
                # (E5a "one event, all surfaces" — a reload must never be
                # needed to see a newly proposed name).
                "nameLlm": name_llm,
            },
        )

    # I7: the summarization plane. Constructed here (not at import time) so
    # each `create_app()` call — including one per test — gets its own queue
    # and worker pool rather than sharing process-wide singletons.
    summary_queue = SummaryQueue(max_depth=settings.queue_max_depth)
    llm_adapter = create_llm_adapter(settings.llm_adapter, settings)
    worker_pool = SummaryWorkerPool(
        queue=summary_queue,
        adapter=llm_adapter,
        session_factory=session_factory,
        concurrency=settings.summary_concurrency,
        result_listener=_publish_summary_event,
    )
    app.state.summary_queue = summary_queue
    app.state.llm_adapter = llm_adapter
    app.state.summary_worker_pool = worker_pool
    worker_pool.start()

    logger.info(
        "startup.ready",
        db_path=settings.db_path,
        revision=revision,
        llm_adapter=llm_adapter.name,
        summary_worker_concurrency=worker_pool.concurrency,
    )

    yield

    await worker_pool.stop()
    await dispose_engine(engine)


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="GraphRev API",
        version="0.1.0",
        lifespan=lifespan,
    )

    dev_origins = ["http://127.0.0.1:5173", "http://localhost:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=dev_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        bind_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
        response.headers["x-request-id"] = request_id
        return response

    # FastAPI's `add_exception_handler` signature is intentionally broad
    # (`Callable[[Request, Exception], ...]`); our handlers are narrowed to
    # their specific exception type for clarity at the call site below, which
    # mypy flags as a variance mismatch even though it is safe in practice.
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(config_router.router, prefix="/api/v1")
    app.include_router(health_router.router, prefix="/api/v1")
    app.include_router(binaries_router.router, prefix="/api/v1")
    app.include_router(functions_router.router, prefix="/api/v1")
    app.include_router(neighbours_router.router, prefix="/api/v1")
    app.include_router(views_router.router, prefix="/api/v1")
    app.include_router(view_nodes_router.router, prefix="/api/v1")
    app.include_router(summaries_router.router, prefix="/api/v1")
    app.include_router(queue_router.router, prefix="/api/v1")
    app.include_router(events_router.router, prefix="/api/v1")

    return app


app = create_app()
