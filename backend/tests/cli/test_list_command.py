"""Tests for the `graphrev list` command."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from revaid.db.models import Edge, Function
from revaid.repositories.binaries import get_or_create_binary
from revaid_contracts.clock import utc_now_iso

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _run_cli(*args: str, db_path: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "GRAPHREV_DB_PATH": db_path,
        "GRAPHREV_PUBLIC_MODE": "false",
        "GRAPHREV_SQLITE_SYNCHRONOUS": "OFF",
    }
    return subprocess.run(
        [sys.executable, "-m", "revaid.cli.__main__", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.asyncio
async def test_list_command_shows_binary_and_analysis_counts(
    migrated_db: Path, session: AsyncSession
) -> None:
    binary, _ = await get_or_create_binary(session, name="sample.exe", version="1.2")
    now = utc_now_iso()
    entry = Function(
        binary_id=binary.id, address=4096, name="entry", created_at=now, updated_at=now
    )
    callee = Function(
        binary_id=binary.id, address=4112, name="callee", created_at=now, updated_at=now
    )
    session.add_all([entry, callee])
    await session.flush()
    session.add(Edge(binary_id=binary.id, caller_id=entry.id, callee_id=callee.id))
    await session.commit()

    result = _run_cli("list", db_path=str(migrated_db))

    assert result.returncode == 0, result.stderr
    assert "sample.exe (1.2)" in result.stdout
    assert "2 functions" in result.stdout
    assert "1 edges" in result.stdout


def test_list_command_reports_empty_database(migrated_db: Path) -> None:
    result = _run_cli("list", db_path=str(migrated_db))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "No binaries ingested."
