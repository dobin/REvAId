"""Viewer database maintenance commands."""

from __future__ import annotations

import asyncio

import typer
from sqlalchemy import text

from revaid_ui.core.config import get_settings
from revaid_ui.db.engine import create_engine, create_session_factory, dispose_engine

app = typer.Typer()


@app.command("viewer-stats")
def viewer_stats() -> None:
    """Print row counts for viewer-owned tables without opening analysis DB."""

    async def _run() -> None:
        settings = get_settings()
        engine = create_engine(settings, db_path=settings.viewer_db_path)
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            for table in ("views", "view_nodes", "binary_ui_state"):
                count = (await session.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one()
                typer.echo(f"{table}: {count}")
        await dispose_engine(engine)

    asyncio.run(_run())
