"""Lifecycle for the standalone analysis service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from revaid.adapters.llm import create_adapter as create_llm_adapter
from revaid.core.config import Settings
from revaid.db.engine import create_engine, create_session_factory, dispose_engine
from revaid.db.revision import read_revision, require_revision
from revaid.db.startup import (
    ANALYSIS_MIGRATION_REVISION,
    recompute_utility_if_threshold_changed,
    recover_pending_summaries,
)
from revaid.events.bus import InProcessEventBus
from revaid.ingestion.import_jobs import ImportJobManager
from revaid.services.queue_service import queue_event_payload_with_items
from revaid.summarization.queue import SummaryQueue
from revaid.summarization.worker import SummaryWorkerPool
from revaid_contracts.logging import configure_logging, get_logger, restore_uvicorn_formatters

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    summary_queue = SummaryQueue(max_depth=settings.queue_max_depth)
    import_job_manager = ImportJobManager(session_factory, settings)
    worker_pool: SummaryWorkerPool | None = None
    try:
        await import_job_manager.start()
        app.state.import_job_manager = import_job_manager
        revision = await read_revision(session_factory, "Analysis")
        require_revision(revision, ANALYSIS_MIGRATION_REVISION, "Analysis")
        async with session_factory() as session:
            await recover_pending_summaries(session, summary_queue)
            await recompute_utility_if_threshold_changed(session, settings)

        event_bus = InProcessEventBus(subscriber_queue_size=settings.sse_subscriber_queue_size)
        app.state.event_bus = event_bus
        app.state.event_loop_role = "analysis"

        async def publish_summary_event(
            *,
            function_id: int,
            binary_id: int,
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
                    "nameLlm": name_llm,
                },
            )

        llm_adapter = create_llm_adapter(settings.llm_adapter, settings)

        async def publish_queue_event() -> None:
            async with session_factory() as session:
                payload = await queue_event_payload_with_items(session, summary_queue)
            event_bus.publish("queue", payload)

        async def publish_llm_status_changed() -> None:
            event_bus.publish("llm-status", {})

        worker_pool = SummaryWorkerPool(
            queue=summary_queue,
            adapter=llm_adapter,
            session_factory=session_factory,
            concurrency=settings.summary_concurrency,
            configured_model=settings.llm_model,
            result_listener=publish_summary_event,
            queue_listener=publish_queue_event,
            outcome_listener=publish_llm_status_changed,
        )
        app.state.summary_queue = summary_queue
        app.state.llm_adapter = llm_adapter
        app.state.summary_worker_pool = worker_pool
        worker_pool.start()
        restore_uvicorn_formatters()
        logger.info(
            "startup.ready",
            db_path=settings.db_path,
            revision=revision,
            llm_adapter=llm_adapter.name,
            summary_worker_concurrency=worker_pool.concurrency,
        )
        yield
    finally:
        await import_job_manager.stop()
        if worker_pool is not None:
            await worker_pool.stop()
        await dispose_engine(engine)
