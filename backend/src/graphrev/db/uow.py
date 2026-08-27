"""Unit-of-work helper with a process-wide write lock (TAD §1.3, B18).

SQLite permits one writer at a time. B18/Q27 declare *no* concurrency control
(no optimistic locking, no version columns) — the write lock exists purely to
avoid ``SQLITE_BUSY`` under the debounced write traffic from drag/camera/notes,
not to serialise conflicting edits. It is **intra-process only**: the ingestion
CLI is a separate process and relies on WAL + ``busy_timeout`` for safety
against the API process, per TAD §2.1.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

#: Process-wide. At the write volumes this app produces (a handful/sec) this
#: lock is effectively always free; it simply eliminates SQLITE_BUSY flakiness.
#:
#: An ``asyncio.Lock`` binds to an event loop once it has waiters, so a single
#: module-level lock is unsafe under pytest-asyncio's function-scoped loops
#: (a later test can raise ``RuntimeError: ... is bound to a different event
#: loop`` while its summary workers persist results). Production runs a single
#: loop, so nothing needs to change there — the test suite resets this lock
#: per test instead (see ``tests/conftest.py::_fresh_write_lock``).
_write_lock = asyncio.Lock()


@asynccontextmanager
async def write_lock() -> AsyncIterator[None]:
    """Serialise a database write with ingestion and background workers.

    Request-scoped sessions are normally safe for reads, but SQLite permits
    only one writer. Write endpoints must hold this lock across their
    read-modify-write transaction so they queue behind a long import instead
    of eventually failing with ``database is locked``.
    """
    async with _write_lock:
        yield


@asynccontextmanager
async def unit_of_work(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Open a session for a write transaction, serialised against other writers.

    Commits on clean exit, rolls back on exception, always releases the lock.
    """
    async with write_lock(), session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
