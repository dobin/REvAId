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

from revaid.core.config import Settings, get_settings
from revaid.db.engine import create_engine, create_session_factory, dispose_engine
from revaid_ui.core.config import Settings as ViewerSettings
from revaid_ui.db.engine import (
    create_engine as create_viewer_engine,
)
from revaid_ui.db.engine import (
    create_session_factory as create_viewer_session_factory,
)
from revaid_ui.db.engine import (
    dispose_engine as dispose_viewer_engine,
)

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
ViewerSettings.model_config["env_file"] = None
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

    ``revaid.db.uow._write_lock`` is a module-level ``asyncio.Lock``. Such a
    lock binds to the event loop that first has a waiter on it, so once one
    test contends on it (e.g. the summary worker pool), a later test running
    on pytest-asyncio's *next* function-scoped loop raises
    ``RuntimeError: ... is bound to a different event loop``. Production uses a
    single loop and never hits this; the suite just rebinds the lock per test.
    """
    import revaid.db.uow as uow
    import revaid_ui.db.uow as viewer_uow

    uow._write_lock = asyncio.Lock()
    viewer_uow._viewer_write_lock = asyncio.Lock()
    yield


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "graphrev-test.db"


@pytest.fixture
def viewer_db_path(tmp_path: Path) -> Path:
    return tmp_path / "graphrev-viewer-test.db"


@pytest.fixture
def settings(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    _purge_graphrev_env()
    monkeypatch.setenv("GRAPHREV_DB_PATH", str(db_path))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def viewer_settings(
    db_path: Path, viewer_db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[ViewerSettings]:
    _purge_graphrev_env()
    monkeypatch.setenv("GRAPHREV_DB_PATH", str(db_path))
    monkeypatch.setenv("GRAPHREV_VIEWER_DB_PATH", str(viewer_db_path))
    yield ViewerSettings()


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


@pytest.fixture(scope="session")
def viewer_migrated_template_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    template = tmp_path_factory.mktemp("viewer-template") / "viewer-template.db"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "viewer_alembic.ini", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**_inherit_env(), "GRAPHREV_VIEWER_DB_PATH": str(template)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"viewer alembic upgrade head failed:\n{result.stdout}\n{result.stderr}"
    )
    assert template.exists()
    return template


@pytest.fixture
def migrated_db(db_path: Path, migrated_template_db: Path) -> Path:
    """Give this test its own copy of the session-migrated template DB."""
    import shutil

    for suffix in ("", "-wal", "-shm"):
        src = Path(str(migrated_template_db) + suffix)
        if src.exists():
            shutil.copyfile(src, Path(str(db_path) + suffix))
    return db_path


@pytest.fixture
def viewer_migrated_db(viewer_db_path: Path, viewer_migrated_template_db: Path) -> Path:
    import shutil

    for suffix in ("", "-wal", "-shm"):
        src = Path(str(viewer_migrated_template_db) + suffix)
        if src.exists():
            shutil.copyfile(src, Path(str(viewer_db_path) + suffix))
    return viewer_db_path


def _inherit_env() -> dict[str, str]:
    import os

    return dict(os.environ)


@pytest_asyncio.fixture
async def engine(migrated_db: Path, settings: Settings) -> AsyncIterator[AsyncEngine]:
    eng = create_engine(settings)
    yield eng
    await dispose_engine(eng)


@pytest_asyncio.fixture
async def viewer_engine(
    viewer_migrated_db: Path, viewer_settings: ViewerSettings
) -> AsyncIterator[AsyncEngine]:
    eng = create_viewer_engine(viewer_settings)
    yield eng
    await dispose_viewer_engine(eng)


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
def viewer_session_factory(viewer_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_viewer_session_factory(viewer_engine)


@pytest_asyncio.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def viewer_session(
    viewer_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with viewer_session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def client(
    migrated_db: Path,
    viewer_migrated_db: Path,
    settings: Settings,
    viewer_settings: ViewerSettings,
) -> AsyncIterator[AsyncClient]:
    """An httpx AsyncClient over the real ASGI app, DB already migrated.

    Uses ASGITransport with ``lifespan="auto"`` semantics via a manual
    lifespan context so the app's own startup hooks (migration-head check,
    C5b recovery, F1b recompute) run exactly as they would under uvicorn.
    """
    import httpx
    from asgi_lifespan import LifespanManager

    from revaid.main import create_app as create_analysis_app
    from revaid_ui.main import create_app as create_viewer_app

    analysis_app = create_analysis_app(settings)
    viewer_app = create_viewer_app(viewer_settings)
    from revaid_ui.analysis.client import HttpAnalysisClient

    analysis_http_client = httpx.AsyncClient(
        base_url="http://analysis-test",
        transport=ASGITransport(app=analysis_app),
        follow_redirects=False,
    )
    viewer_app.state.analysis_client = HttpAnalysisClient(
        viewer_settings.analysis_internal_url,
        timeout_seconds=viewer_settings.analysis_request_timeout_seconds,
        max_response_bytes=viewer_settings.analysis_max_response_bytes,
        token=viewer_settings.analysis_internal_token,
        client=analysis_http_client,
    )
    async with (
        LifespanManager(analysis_app),
        LifespanManager(viewer_app),
    ):
        try:

            class ServiceTransport(httpx.AsyncBaseTransport):
                app = viewer_app

                async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                    target = (
                        analysis_app if request.url.path.startswith("/internal/") else viewer_app
                    )
                    return await ASGITransport(
                        app=target, raise_app_exceptions=False
                    ).handle_async_request(request)

            transport = ServiceTransport()
            transport.app = viewer_app
            transport.analysis_app = analysis_app

            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
        finally:
            await viewer_app.state.analysis_client.aclose()
