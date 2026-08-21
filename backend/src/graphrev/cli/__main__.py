"""``graphrev`` Typer CLI entry point (A1)."""

from __future__ import annotations

import typer

from graphrev.cli import dbtools
from graphrev.cli import ingest as ingest_module

app = typer.Typer(help="GraphRev command-line tools.")
app.add_typer(dbtools.app, name="db")


@app.command()
def ingest(
    adapter: str = typer.Option("mock", help="Ghidra adapter to use: mock | rest."),
    seed: int = typer.Option(1337, help="PRNG seed for the mock adapter (A2)."),
    binary: str | None = typer.Option(
        None, help="Binary name to ingest (mock adapter default set)."
    ),
) -> None:
    """Ingest a binary (A1)."""
    ingest_module.run(adapter=adapter, seed=seed, binary=binary)


if __name__ == "__main__":
    app()
