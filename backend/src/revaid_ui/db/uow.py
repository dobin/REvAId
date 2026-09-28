"""Viewer SQLite write serialization."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

_viewer_write_lock = asyncio.Lock()


@asynccontextmanager
async def viewer_write_lock() -> AsyncIterator[None]:
    async with _viewer_write_lock:
        yield


@asynccontextmanager
async def unit_of_work(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with viewer_write_lock(), session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
