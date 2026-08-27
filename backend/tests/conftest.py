"""Shared pytest fixtures.

Uses a temp-file SQLite DB (not ``:memory:``) because Alembic + WAL need a real
file on disk. ``alembic upgrade head`` is run programmatically so tests exercise
the exact same migration path as `just migrate`.
"""

from __future__ import annotations

import asyncio
import os
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

# ---------------------------------------------------------------------------
# Hermetic config: tests must not see a developer's `backend/.env`.
#
# Two distinct leakage paths, both observed live:
#
# 1. `Settings` declares `env_file=".env"` (resolved against the process
#    cwd, i.e. `backend/` under `uv run pytest`), so a developer's real
#    config would override the defaults the tests assert on.
# 2. **Importing `litellm` loads `.env` from the cwd and exports every entry
#    into `os.environ`** — real environment variables, which beat everything
#    in pydantic-settings' source order. The litellm adapter tests import it,
#    so the poison arrives mid-session, after any import-time cleanup.
#
# Therefore: disable the dotenv source at conftest import time (before any
# test instantiates `Settings`), and purge `GRAPHREV_*` from `os.environ`
# both at import time and in the `settings` fixture (which runs after the
# litellm tests may have already polluted it). `monkeypatch.setenv` in
# individual override tests still works — it re-adds vars after the purge.
# ---------------------------------------------------------------------------
Settings.model_config["env_file"] = None
get_settings.cache_clear()
for _key in [k for k in os.environ if k.startswith("GRAPHREV_")]:
    del os.environ[_key]


def _purge_graphrev_env() -> None:
    """Remove `GRAPHREV_*` vars that `import litellm` may have exported from a
    developer's `.env` after this conftest was imported (see block above)."""
    for key in [k for k in os.environ if k.startswith("GRAPHREV_")]:
        del os.environ[key]


@pytest.fixture(autouse=True)
def _fresh_write_lock() -> Iterator[None]:
    """Give every test a fresh SQLite writer lock.

    ``graphrev.db.uow._write_lock`` is a module-level ``asyncio.Lock``. Such a
    lock binds to the event loop that first has a waiter on it, so once one
    test contends on it (e.g. the summary worker pool), a later test running
    on pytest-asyncio's *next* function-scoped loop raises
    ``RuntimeError: ... is bound to a different event loop``. Production uses a
    single loop and never hits this; the suite just rebinds the lock per test.
    """
    import graphrev.db.uow as uow

    uow._write_lock = asyncio.Lock()
    yield


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "graphrev-test.db"


@pytest.fixture
def settings(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    _purge_graphrev_env()
    monkeypatch.setenv("GRAPHREV_DB_PATH", str(db_path))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def migrated_template_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Run `alembic upgrade head` ONCE per session into a template DB.

    Migrating a fresh SQLite file per test (a subprocess interpreter boot +
    the full migration chain each time) dominated the suite's wall time.
    Tests instead copy this template file — the migration path under test
    is still the exact one `just migrate` runs, just amortised.
    """
    template = tmp_path_factory.mktemp("template") / "graphrev-template.db"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        # Explicit path LAST: `settings` may have monkeypatch.setenv'd
        # GRAPHREV_DB_PATH by the time this session fixture first runs, and
        # it must not override the template path.
        env={**_inherit_env(), "GRAPHREV_DB_PATH": str(template)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"alembic upgrade head failed:\n{result.stdout}\n{result.stderr}"
    assert template.exists(), "alembic reported success but created no template DB"
    return template


@pytest.fixture
def migrated_db(settings: Settings, migrated_template_db: Path) -> Path:
    """Give this test its own copy of the session-migrated template DB."""
    import shutil

    for suffix in ("", "-wal", "-shm"):
        src = Path(str(migrated_template_db) + suffix)
        if src.exists():
            shutil.copyfile(src, Path(str(settings.db_path) + suffix))
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
