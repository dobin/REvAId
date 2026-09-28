"""The TAD's literal I2 exit test, run through the real `graphrev` CLI
entrypoint (not just the pipeline function): double-run idempotency,
analyst-field survival across re-ingestion, and a clean failure for
`--adapter rest`."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _run_cli(*args: str, db_path: str) -> subprocess.CompletedProcess[str]:
    # Disposable test DB: skip fsyncs (the ingest's ~1k statements over the
    # async driver dominate CLI-test wall time). Pin private mode as well:
    # importing LiteLLM can repopulate GRAPHREV_* variables from a developer's
    # .env after the parent test fixture performed its environment cleanup.
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


@pytest.mark.slow
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


@pytest.mark.slow
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


@pytest.mark.slow
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


def test_import_export_unmigrated_database_reports_migration_command(tmp_path: Path) -> None:
    export_path = tmp_path / "export.json"
    export_path.write_text("{}", encoding="utf-8")
    db_path = tmp_path / "unmigrated.db"

    result = _run_cli("import-export", str(export_path), db_path=str(db_path))

    assert result.returncode == 1
    assert "graphrev db migrate-analysis" in result.stderr
    assert "no such table: binaries" not in result.stderr


def test_decompile_unmigrated_database_skips_kuna(tmp_path: Path) -> None:
    binary_path = tmp_path / "sample.exe"
    binary_path.write_bytes(b"MZ test binary")
    marker_path = tmp_path / "kuna-was-run"
    executable = tmp_path / "fake-kuna"
    executable.write_text(
        f"#!/bin/sh\ntouch {shlex.quote(str(marker_path))}\nexit 0\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    env = {
        **os.environ,
        "GRAPHREV_DB_PATH": str(tmp_path / "unmigrated.db"),
        "GRAPHREV_DECOMPILER_EXECUTABLE": str(executable),
        "GRAPHREV_IMPORT_STAGING_DIR": str(tmp_path / "staging"),
        "HOME": str(tmp_path),
    }

    result = subprocess.run(
        [sys.executable, "-m", "revaid.cli.__main__", "decompile", str(binary_path)],
        cwd=BACKEND_DIR.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "graphrev db migrate-analysis" in result.stderr
    assert "no such table: binaries" not in result.stderr
    assert not marker_path.exists()


def test_migrate_analysis_and_import_share_relative_db_path(tmp_path: Path) -> None:
    export_path = tmp_path / "export.json"
    export_path.write_text(
        '{"schemaVersion":4,"binary":{"name":"relative-db-test","version":""},'
        '"functions":[],"edges":[]}',
        encoding="utf-8",
    )
    relative_db_path = Path(os.path.relpath(tmp_path / "relative.db", BACKEND_DIR))
    env = {
        **os.environ,
        "GRAPHREV_DB_PATH": str(relative_db_path),
        "GRAPHREV_PUBLIC_MODE": "false",
        "GRAPHREV_SQLITE_SYNCHRONOUS": "OFF",
    }

    migration = subprocess.run(
        [sys.executable, "-m", "revaid.cli.__main__", "db", "migrate-analysis"],
        cwd=BACKEND_DIR.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert migration.returncode == 0, migration.stderr

    imported = subprocess.run(
        [sys.executable, "-m", "revaid.cli.__main__", "import-export", str(export_path)],
        cwd=BACKEND_DIR.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert imported.returncode == 0, imported.stderr
    assert "Imported relative-db-test" in imported.stdout
    assert (BACKEND_DIR / relative_db_path).exists()


@pytest.mark.asyncio
async def test_headless_decompile_imports_kuna_export(
    migrated_db: Path,
    viewer_migrated_db: Path,
    tmp_path: Path,
    engine: AsyncEngine,
    viewer_engine: AsyncEngine,
) -> None:
    binary_path = tmp_path / "sample.exe"
    binary_path.write_bytes(b"MZ test binary")
    export = (
        '{"schemaVersion":4,"binary":{"name":"from-kuna","version":""},'
        '"functions":[{"address":4096,"name":"entry","isEntryPoint":true}],'
        '"edges":[]}'
    )
    staging_dir = tmp_path / "staging"
    env = {
        **os.environ,
        "GRAPHREV_DB_PATH": str(migrated_db),
        "GRAPHREV_VIEWER_DB_PATH": str(viewer_migrated_db),
        "GRAPHREV_PUBLIC_MODE": "false",
        "GRAPHREV_SQLITE_SYNCHRONOUS": "OFF",
        "GRAPHREV_DECOMPILER_EXECUTABLE": "~/fake-kuna",
        "GRAPHREV_IMPORT_STAGING_DIR": str(staging_dir),
        "HOME": str(tmp_path),
    }
    executable = tmp_path / "fake-kuna"
    executable.write_text(
        "#!/bin/sh\n"
        'test "$1" = decompile-graph || exit 2\n'
        f"cat > \"$4\" <<'JSON'\n{export}\nJSON\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    result = subprocess.run(
        [sys.executable, "-m", "revaid.cli.__main__", "decompile", str(binary_path)],
        cwd=BACKEND_DIR.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Analyzed and imported sample.exe" in result.stdout

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT b.name, b.sha256, f.name FROM binaries b "
                    "JOIN functions f ON f.binary_id = b.id"
                )
            )
        ).one()
    async with viewer_engine.connect() as conn:
        view_count = (await conn.execute(text("SELECT COUNT(*) FROM views"))).scalar_one()
    assert row[0] == "sample.exe"
    assert row[1] is not None and len(row[1]) == 64
    assert row[2] == "entry"
    assert view_count == 0


def test_decompile_missing_input_reports_path_and_skips_kuna(tmp_path: Path) -> None:
    missing_binary = tmp_path / "missing.exe"
    executable = tmp_path / "fake-kuna"
    executable.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    executable.chmod(0o755)
    env = {
        **os.environ,
        "GRAPHREV_DECOMPILER_EXECUTABLE": str(executable),
        "HOME": str(tmp_path),
    }

    result = subprocess.run(
        [sys.executable, "-m", "revaid.cli.__main__", "decompile", str(missing_binary)],
        cwd=BACKEND_DIR.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert f"Input binary does not exist: {missing_binary}" in result.stderr
    assert "Kuna command:" not in result.stderr


def test_decompile_kuna_failure_reports_full_command(tmp_path: Path) -> None:
    binary_path = tmp_path / "sample binary.exe"
    binary_path.write_bytes(b"MZ test binary")
    executable = tmp_path / "fake-kuna"
    executable.write_text(
        "#!/bin/sh\necho 'kuna failed'\nexit 7\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    staging_dir = tmp_path / "staging dir"
    env = {
        **os.environ,
        "GRAPHREV_DECOMPILER_EXECUTABLE": str(executable),
        "GRAPHREV_IMPORT_STAGING_DIR": str(staging_dir),
        "HOME": str(tmp_path),
    }

    result = subprocess.run(
        [sys.executable, "-m", "revaid.cli.__main__", "decompile", str(binary_path)],
        cwd=BACKEND_DIR.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Kuna command:" in result.stderr
    assert "decompile-graph" in result.stderr
    assert shlex.quote(str(binary_path.resolve())) in result.stderr
    assert "kuna failed" in result.stderr
