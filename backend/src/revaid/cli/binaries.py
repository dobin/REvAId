"""Binary-listing CLI commands."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path

import typer

from revaid.core.config import get_settings
from revaid.db.engine import create_engine, create_session_factory, dispose_engine
from revaid.db.revision import MigrationNotAppliedError, read_revision, require_revision
from revaid.db.startup import ANALYSIS_MIGRATION_REVISION
from revaid.repositories.binaries import BinaryWithCounts, list_binaries


def _format_binary(row: BinaryWithCounts) -> str:
    """Format one binary with concise counts and available file size."""
    binary = row.binary
    size = "unknown"
    if binary.source_path:
        with suppress(OSError):
            size = _format_size(Path(binary.source_path).stat().st_size)
    version = f" ({binary.version})" if binary.version else ""
    return f"{binary.name}{version}  {size}  {row.function_count} functions  {row.edge_count} edges"


def _format_size(size: int) -> str:
    """Render byte counts using readable binary units."""
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def run() -> None:
    """Print every ingested binary with file size, function count, and edge count."""
    settings = get_settings()

    async def _run() -> None:
        engine = create_engine(settings)
        session_factory = create_session_factory(engine)
        try:
            try:
                revision = await read_revision(session_factory, "Analysis")
                require_revision(revision, ANALYSIS_MIGRATION_REVISION, "Analysis")
            except MigrationNotAppliedError as exc:
                typer.echo(str(exc), err=True)
                raise typer.Exit(code=1) from exc

            async with session_factory() as session:
                rows = await list_binaries(session)
        finally:
            await dispose_engine(engine)

        if not rows:
            typer.echo("No binaries ingested.")
            return

        typer.echo("BINARY  SIZE  FUNCTIONS  EDGES")
        for row in rows:
            typer.echo(_format_binary(row))

    asyncio.run(_run())
