"""Async engine + PRAGMAs + session factory (TAD §1.3).

SQLite resets ``PRAGMA foreign_keys`` **per connection** — it is not a database-
wide setting — so B17's FK integrity guarantee depends on the ``connect`` event
listener below firing for every new connection, not just the first one.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry

from graphrev.core.config import Settings


def _sqlite_url(db_path: str) -> str:
    return f"sqlite+aiosqlite:///{db_path}"


def create_engine(settings: Settings) -> AsyncEngine:
    engine = create_async_engine(_sqlite_url(settings.db_path), future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection: Any, _connection_record: ConnectionPoolEntry) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA synchronous={settings.sqlite_synchronous}")
        cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms}")
        cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def dispose_engine(engine: AsyncEngine) -> None:
    await engine.dispose()


async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Plain read-only session context. Writers should use :mod:`graphrev.db.uow`."""
    async with session_factory() as session:
        yield session
