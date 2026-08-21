"""The TAD's literal I2 exit test, run through the real `graphrev` CLI
entrypoint (not just the pipeline function): double-run idempotency,
analyst-field survival across re-ingestion, and a clean failure for
`--adapter rest`."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _run_cli(*args: str, db_path: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GRAPHREV_DB_PATH": db_path}
    return subprocess.run(
        [sys.executable, "-m", "graphrev.cli.__main__", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.asyncio
async def test_ingest_command_twice_is_idempotent(migrated_db: Path, engine: AsyncEngine) -> None:
    db_path = str(migrated_db)

    result1 = _run_cli("ingest", "--adapter", "mock", "--seed", "1337", db_path=db_path)
    assert result1.returncode == 0, result1.stderr

    async with engine.connect() as conn:
        count1 = (await conn.execute(text("SELECT COUNT(*) FROM functions"))).scalar_one()

    result2 = _run_cli("ingest", "--adapter", "mock", "--seed", "1337", db_path=db_path)
    assert result2.returncode == 0, result2.stderr

    async with engine.connect() as conn:
        count2 = (await conn.execute(text("SELECT COUNT(*) FROM functions"))).scalar_one()

    assert count1 == count2
    assert "functions:" in result1.stdout
    assert "0 per-item failures" in result1.stdout


@pytest.mark.asyncio
async def test_ingest_command_preserves_analyst_fields_on_third_run(
    migrated_db: Path, engine: AsyncEngine
) -> None:
    db_path = str(migrated_db)
    _run_cli("ingest", "--adapter", "mock", "--seed", "1337", db_path=db_path)

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE functions SET name_analyst = 'parse_config', "
                "notes = 'analyst note', utility_override = 'never', "
                "summary_short = 'a cached summary' "
                "WHERE address = 0x00401000"
            )
        )

    result3 = _run_cli("ingest", "--adapter", "mock", "--seed", "1337", db_path=db_path)
    assert result3.returncode == 0, result3.stderr

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT name_analyst, notes, utility_override, summary_short "
                    "FROM functions WHERE address = 0x00401000"
                )
            )
        ).one()

    assert row.name_analyst == "parse_config"
    assert row.notes == "analyst note"
    assert row.utility_override == "never"
    assert row.summary_short == "a cached summary"


@pytest.mark.asyncio
async def test_ingest_command_preserves_is_entry_point_override_on_third_run(
    migrated_db: Path, engine: AsyncEngine
) -> None:
    """I3/E1b: `is_entry_point` is analyst-owned, like `utility_override` —
    once an analyst flips it, re-ingestion must never overwrite it, even for
    a function the mock adapter itself flags as an entry point (`main`)."""
    db_path = str(migrated_db)
    _run_cli("ingest", "--adapter", "mock", "--seed", "1337", db_path=db_path)

    async with engine.connect() as conn:
        seeded = (
            await conn.execute(
                text("SELECT is_entry_point FROM functions WHERE address = 0x00401000")
            )
        ).scalar_one()
    assert bool(seeded) is True  # `main` is seeded true by the mock adapter

    async with engine.begin() as conn:
        # Analyst turns it off for `main` and turns it on for an unrelated
        # function that the adapter never flags.
        await conn.execute(
            text("UPDATE functions SET is_entry_point = 0 WHERE address = 0x00401000")
        )
        await conn.execute(
            text("UPDATE functions SET is_entry_point = 1 WHERE address = 0x00401020")
        )

    result3 = _run_cli("ingest", "--adapter", "mock", "--seed", "1337", db_path=db_path)
    assert result3.returncode == 0, result3.stderr

    async with engine.connect() as conn:
        main_flag = (
            await conn.execute(
                text("SELECT is_entry_point FROM functions WHERE address = 0x00401000")
            )
        ).scalar_one()
        other_flag = (
            await conn.execute(
                text("SELECT is_entry_point FROM functions WHERE address = 0x00401020")
            )
        ).scalar_one()

    assert bool(main_flag) is False
    assert bool(other_flag) is True


def test_ingest_command_rest_adapter_exits_nonzero(migrated_db: Path) -> None:
    result = _run_cli("ingest", "--adapter", "rest", db_path=str(migrated_db))
    assert result.returncode != 0
    assert "not implemented" in result.stderr.lower()
