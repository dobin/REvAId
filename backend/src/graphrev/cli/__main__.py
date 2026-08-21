"""``graphrev`` Typer CLI entry point (A1)."""

from __future__ import annotations

import typer

from graphrev.cli import dbtools

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
    """Ingest a binary. Not implemented until Increment I2."""
    typer.echo(
        "graphrev ingest is not implemented yet — it arrives in TAD Increment I2 "
        "(mock Ghidra adapter + ingestion pipeline).",
        err=True,
    )
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
