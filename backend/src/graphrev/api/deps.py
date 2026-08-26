"""Dependency-injection providers.

Routers stay thin (TAD principle #2) by depending on these ``Annotated``
aliases rather than constructing sessions/settings themselves.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graphrev.adapters.llm.base import LlmAdapter
from graphrev.core.config import Settings, get_settings
from graphrev.db.uow import write_lock
from graphrev.events.bus import InProcessEventBus
from graphrev.ingestion.import_jobs import ImportJobManager
from graphrev.summarization.queue import SummaryQueue


def get_settings_dep() -> Settings:
    return get_settings()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


async def get_write_session(request: Request) -> AsyncIterator[AsyncSession]:
    """A request session serialised with every other SQLite writer.

    Services retain responsibility for commit/rollback, matching `get_session`.
    Holding the lock for the entire endpoint prevents a read-modify-write
    request from racing a long `unit_of_work` ingestion transaction.
    """
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with write_lock(), session_factory() as session:
        yield session


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    """The process session factory (I12).

    The ingestion pipeline opens its own ``unit_of_work`` transactions, so an
    import endpoint needs the *factory*, not a single request-scoped session.
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return factory


def get_summary_queue(request: Request) -> SummaryQueue:
    """The process-wide `SummaryQueue` (I7), constructed once in the lifespan
    and shared by every router and the worker pool."""
    queue: SummaryQueue = request.app.state.summary_queue
    return queue


def get_event_bus(request: Request) -> InProcessEventBus:
    """The process-wide `EventBus` (I8), constructed once in the lifespan and
    shared by every router and the worker pool's result listener."""
    bus: InProcessEventBus = request.app.state.event_bus
    return bus


def get_llm_adapter(request: Request) -> LlmAdapter:
    """The process-wide `LlmAdapter` (I7/I13), constructed once in the
    lifespan. Routers depend on the Protocol from ``adapters/llm/base`` —
    never a concrete adapter (import-linter)."""
    adapter: LlmAdapter = request.app.state.llm_adapter
    return adapter


def get_import_job_manager(request: Request) -> ImportJobManager:
    manager: ImportJobManager = request.app.state.import_job_manager
    return manager


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
WriteSessionDep = Annotated[AsyncSession, Depends(get_write_session)]
SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
SummaryQueueDep = Annotated[SummaryQueue, Depends(get_summary_queue)]
EventBusDep = Annotated[InProcessEventBus, Depends(get_event_bus)]
LlmAdapterDep = Annotated[LlmAdapter, Depends(get_llm_adapter)]
ImportJobManagerDep = Annotated[ImportJobManager, Depends(get_import_job_manager)]
