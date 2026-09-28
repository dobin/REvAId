"""``graphrev`` Typer CLI entry point (A1)."""

from __future__ import annotations

from pathlib import Path

import typer

from revaid.cli import binaries as binaries_module
from revaid.cli import dbtools
from revaid.cli import ingest as ingest_module

app = typer.Typer(help="GraphRev command-line tools.")
app.add_typer(dbtools.app, name="db")


@app.command()
def ingest(
    adapter: str = typer.Option("mock", help="Analysis adapter to use: mock."),
    seed: int = typer.Option(1337, help="PRNG seed for the mock adapter (A2)."),
    binary: str | None = typer.Option(
        None, help="Binary name to ingest (mock adapter default set)."
    ),
) -> None:
    """Ingest a binary (A1)."""
    ingest_module.run(adapter=adapter, seed=seed, binary=binary)


@app.command()
def list() -> None:
    """List ingested binaries and their analysis statistics."""
    binaries_module.run()


@app.command("import-export")
def import_export(path: Path) -> None:
    """Import a supported analysis-export JSON file."""
    ingest_module.run_import(path)


@app.command()
def decompile(
    path: Path,
    name: str | None = typer.Option(None, help="Stored binary name (defaults to filename)."),
    version: str = typer.Option("", help="Stored binary version."),
) -> None:
    """Analyze a raw binary with GRAPHREV_DECOMPILER_EXECUTABLE and ingest it."""
    ingest_module.run_decompile(path, name, version)


if __name__ == "__main__":
    app()
