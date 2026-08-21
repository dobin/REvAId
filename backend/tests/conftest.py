"""Shared pytest fixtures.

Uses a temp-file SQLite DB (not ``:memory:``) because Alembic + WAL need a real
file on disk. ``alembic upgrade head`` is run programmatically so tests exercise
the exact same migration path as `just migrate`.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from graphrev.core.config import Settings, get_settings
from graphrev.db.engine import create_engine, create_session_factory, dispose_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "graphrev-test.db"


@pytest.fixture
def settings(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    monkeypatch.setenv("GRAPHREV_DB_PATH", str(db_path))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def migrated_db(settings: Settings) -> Path:
    """Run `alembic upgrade head` against `settings.db_path` and return it."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={"GRAPHREV_DB_PATH": settings.db_path, **_inherit_env()},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"alembic upgrade head failed:\n{result.stdout}\n{result.stderr}"
    return Path(settings.db_path)


def _inherit_env() -> dict[str, str]:
    import os

    return dict(os.environ)


@pytest_asyncio.fixture
async def engine(migrated_db: Path, settings: Settings) -> AsyncIterator[AsyncEngine]:
    eng = create_engine(settings)
    yield eng
    await dispose_engine(eng)


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest_asyncio.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def client(migrated_db: Path, settings: Settings) -> AsyncIterator[AsyncClient]:
    """An httpx AsyncClient over the real ASGI app, DB already migrated.

    Uses ASGITransport with ``lifespan="auto"`` semantics via a manual
    lifespan context so the app's own startup hooks (migration-head check,
    C5b recovery, F1b recompute) run exactly as they would under uvicorn.
    """
    from asgi_lifespan import LifespanManager

    from graphrev.main import create_app

    app = create_app()
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac,
    ):
        yield ac
