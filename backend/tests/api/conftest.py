"""Shared fixtures for `tests/api` — a DB pre-populated with the mock binaries
via the real ingestion pipeline, exercised over HTTP through the `client`
fixture (see `tests/conftest.py`)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graphrev.adapters.ghidra.mock import MockGhidraAdapter
from graphrev.core.config import Settings
from graphrev.ingestion.pipeline import run_ingestion

SEED = 1337


@pytest_asyncio.fixture
async def ingested(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> AsyncIterator[None]:
    """Run the real mock-adapter ingestion pipeline once against the test DB
    that both `session_factory` and the `client` fixture point at (same
    `settings.db_path`), so API tests exercise real `acme.exe`/`libparse.dll`
    data end to end."""
    adapter = MockGhidraAdapter(seed=SEED)
    await run_ingestion(session_factory, adapter, settings)
    yield
