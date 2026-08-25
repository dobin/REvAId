"""Shared fixtures for `tests/api` — a DB pre-populated with the mock binaries
via the real ingestion pipeline, exercised over HTTP through the `client`
fixture (see `tests/conftest.py`).

Performance: the mock ingestion produces ~500 functions + ~500 edges across two
binaries, each function/edge upsert wrapped in its own SAVEPOINT. Running that
per test dominated the api suite's wall time (2-5s of *setup* per test). The
mock adapter is fully deterministic (seed-based), so — exactly like the
session-scoped `migrated_template_db` in the parent conftest — we ingest ONCE
into a session-scoped template DB file and copy that file per test instead of
re-running the pipeline. The pipeline itself is still exercised end to end,
just once per session rather than once per test.

Ordering note (why the seed happens inside `migrated_db`, not in `ingested`):
the DB file MUST be seeded before any engine/client opens a connection to
`settings.db_path`; copying a SQLite file out from under an open (WAL) handle
corrupts the reader's view. `migrated_db` is the single point where the test's
DB file is produced, and every DB-opening fixture (`engine`, `session`,
`client`) transitively depends on it — so seeding here guarantees the copy
lands first. We look at `request.fixturenames` to decide whether this test
wants the ingested snapshot (`ingested` requested) or the bare schema.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from graphrev.adapters.ghidra.mock import MockGhidraAdapter
from graphrev.core.config import Settings, get_settings
from graphrev.db.engine import create_engine, create_session_factory, dispose_engine
from graphrev.ingestion.pipeline import run_ingestion

SEED = 1337


@pytest_asyncio.fixture(scope="session")
async def ingested_template_db(migrated_template_db: Path) -> Path:
    """Run the real mock-adapter ingestion pipeline ONCE per session into a
    template DB file, so per-test setup is a cheap file copy rather than a full
    re-ingestion (~1k SAVEPOINT round-trips) every single time.

    Starts from the migrated (schema-only) template, ingests the deterministic
    mock binaries, then checkpoints + disposes the engine so the on-disk `.db`
    file is a self-contained, copyable snapshot.
    """
    template = migrated_template_db.parent / "graphrev-ingested-template.db"
    for suffix in ("", "-wal", "-shm"):
        src = Path(str(migrated_template_db) + suffix)
        if src.exists():
            shutil.copyfile(src, Path(str(template) + suffix))

    prev = os.environ.get("GRAPHREV_DB_PATH")
    os.environ["GRAPHREV_DB_PATH"] = str(template)
    try:
        get_settings.cache_clear()
        template_settings = get_settings()
        engine = create_engine(template_settings)
        try:
            session_factory = create_session_factory(engine)
            adapter = MockGhidraAdapter(seed=SEED)
            await run_ingestion(session_factory, adapter, template_settings)
            # Checkpoint the WAL into the main db file so a plain copy of the
            # `.db` is a complete snapshot even if the sidecars are dropped.
            async with engine.begin() as conn:
                await conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            await dispose_engine(engine)
    finally:
        if prev is None:
            os.environ.pop("GRAPHREV_DB_PATH", None)
        else:
            os.environ["GRAPHREV_DB_PATH"] = prev
        get_settings.cache_clear()

    return template


def _seed_test_db(*, db_path: str, source_template: Path) -> None:
    """Copy a template DB (and its WAL/SHM sidecars, if any) onto the test's
    `db_path`, dropping any stale sidecars the source doesn't have."""
    for suffix in ("", "-wal", "-shm"):
        dst = Path(str(db_path) + suffix)
        src = Path(str(source_template) + suffix)
        if src.exists():
            shutil.copyfile(src, dst)
        elif dst.exists():
            dst.unlink()


@pytest.fixture
def migrated_db(
    request: pytest.FixtureRequest,
    settings: Settings,
    migrated_template_db: Path,
) -> Path:
    """Override of the parent `migrated_db` for `tests/api`.

    Seeds the test DB from the *ingested* template when the test requests the
    `ingested` fixture, otherwise from the bare *migrated* (schema-only)
    template — identically to the parent fixture. Doing the copy here (the
    single producer of the test DB file) guarantees it happens before any
    engine/client opens the file, avoiding SQLite corruption from copying
    under an open WAL handle.
    """
    if "ingested" in request.fixturenames:
        source: Path = request.getfixturevalue("ingested_template_db")
    else:
        source = migrated_template_db
    _seed_test_db(db_path=str(settings.db_path), source_template=source)
    return Path(settings.db_path)


@pytest_asyncio.fixture
async def ingested(migrated_db: Path) -> AsyncIterator[None]:
    """Marker fixture: its presence in a test's signature makes the `migrated_db`
    override above seed from the ingested snapshot. The actual copy is performed
    by `migrated_db` so it lands before any DB connection is opened."""
    yield
