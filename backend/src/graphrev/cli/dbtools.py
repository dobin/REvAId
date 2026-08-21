"""``graphrev db ...`` subcommands (init / migrate / stats / vacuum)."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import typer
from sqlalchemy import text

from graphrev.core.config import get_settings
from graphrev.db.engine import create_engine, create_session_factory, dispose_engine

app = typer.Typer(help="Database maintenance commands.")


def _alembic_command(*args: str) -> int:
    backend_dir = Path(__file__).resolve().parents[3]
    result = subprocess.run(["alembic", *args], cwd=backend_dir, check=False)
    return result.returncode


@app.command()
def init() -> None:
    """Alias for `migrate` — this app never creates tables outside Alembic."""
    raise SystemExit(_alembic_command("upgrade", "head"))


@app.command()
def migrate() -> None:
    """Run `alembic upgrade head`."""
    raise SystemExit(_alembic_command("upgrade", "head"))


@app.command()
def stats() -> None:
    """Print row counts for every table."""

    async def _run() -> None:
        settings = get_settings()
        engine = create_engine(settings)
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            for table in ("binaries", "functions", "edges", "views", "view_nodes"):
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
