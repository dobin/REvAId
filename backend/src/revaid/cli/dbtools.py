"""``graphrev db ...`` subcommands (init / migrate / stats / vacuum)."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import typer
from sqlalchemy import text

from revaid.core.config import get_settings
from revaid.db.engine import create_engine, create_session_factory, dispose_engine

app = typer.Typer(help="Database maintenance commands.")


def _alembic_command(*args: str) -> int:
    backend_dir = Path(__file__).resolve().parents[3]
    result = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=backend_dir, check=False)
    return result.returncode


@app.command()
def init() -> None:
    """Alias for `migrate` — this app never creates tables outside Alembic."""
    raise SystemExit(_alembic_command("upgrade", "head"))


@app.command()
def migrate() -> None:
    """Upgrade analysis and viewer databases."""
    analysis_code = _alembic_command("upgrade", "head")
    if analysis_code != 0:
        raise SystemExit(analysis_code)
    raise SystemExit(_alembic_command("-c", "viewer_alembic.ini", "upgrade", "head"))


@app.command("migrate-analysis")
def migrate_analysis() -> None:
    """Upgrade only the analysis database (standalone analysis-backend deployment)."""
    raise SystemExit(_alembic_command("upgrade", "head"))


@app.command("migrate-viewer")
def migrate_viewer() -> None:
    """Upgrade only the viewer database (standalone viewer-backend deployment)."""
    raise SystemExit(_alembic_command("-c", "viewer_alembic.ini", "upgrade", "head"))


@app.command()
def stats() -> None:
    """Print row counts for every table."""

    async def _run() -> None:
        settings = get_settings()
        engine = create_engine(settings)
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            for table in ("binaries", "functions", "edges"):
                count = (await session.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one()
                typer.echo(f"{table}: {count}")
        await dispose_engine(engine)

    asyncio.run(_run())


@app.command()
def vacuum() -> None:
    """Run SQLite VACUUM to reclaim space."""

    async def _run() -> None:
        settings = get_settings()
        engine = create_engine(settings)
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            await session.execute(text("VACUUM"))
            await session.commit()
        await dispose_engine(engine)

    asyncio.run(_run())
    typer.echo("VACUUM complete.", file=sys.stderr)
