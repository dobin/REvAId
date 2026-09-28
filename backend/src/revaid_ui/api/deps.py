"""Strict dependency providers for the viewer service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revaid_contracts.analysis import AnalysisClient
from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_ui.core.config import Settings
from revaid_ui.db.uow import viewer_write_lock
from revaid_ui.events.bus import InProcessEventBus


def get_settings_dep(request: Request) -> Settings:
    return Settings()


def get_analysis_client(request: Request) -> AnalysisClient:
    client = getattr(request.app.state, "analysis_client", None)
    if client is None:
        raise AppError(ErrorCode.ANALYSIS_UNAVAILABLE, "Analysis service is not configured.")
    return cast(AnalysisClient, client)


async def get_viewer_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.viewer_session_factory
    async with factory() as session:
        yield session


async def get_viewer_write_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.viewer_session_factory
    async with viewer_write_lock(), factory() as session:
        yield session


def get_event_bus(request: Request) -> InProcessEventBus:
    return cast(InProcessEventBus, request.app.state.event_bus)


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
AnalysisClientDep = Annotated[AnalysisClient, Depends(get_analysis_client)]
ViewerSessionDep = Annotated[AsyncSession, Depends(get_viewer_session)]
ViewerWriteSessionDep = Annotated[AsyncSession, Depends(get_viewer_write_session)]
EventBusDep = Annotated[InProcessEventBus, Depends(get_event_bus)]
