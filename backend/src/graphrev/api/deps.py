"""Dependency-injection providers.

Routers stay thin (TAD principle #2) by depending on these ``Annotated``
aliases rather than constructing sessions/settings themselves.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graphrev.core.config import Settings, get_settings


def get_settings_dep() -> Settings:
    return get_settings()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    """The process session factory (I12).

    The ingestion pipeline opens its own ``unit_of_work`` transactions, so an
    import endpoint needs the *factory*, not a single request-scoped session.
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return factory


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
