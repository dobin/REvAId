"""Per-binary ingestion report + console rendering (A4).

Ingestion reports counts and per-function failures without aborting the
whole run — this module is where those counts and failures are collected and
printed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import typer


@dataclass
class BinaryIngestionReport:
    """Outcome of ingesting one binary."""

    binary_name: str
    functions_inserted: int = 0
    functions_updated: int = 0
    edges_inserted: int = 0
    edges_skipped_duplicate: int = 0
    placeholders_created: int = 0
    failures: list[str] = field(default_factory=list)
    binary_failed: bool = False

    @property
    def total_functions(self) -> int:
        return self.functions_inserted + self.functions_updated

    @property
    def failure_count(self) -> int:
        return len(self.failures)


def print_report(reports: list[BinaryIngestionReport]) -> None:
    """A4: render counts and failures for every binary in this run."""
    for r in reports:
        status = "FAILED" if r.binary_failed else "ok"
        typer.echo(f"== {r.binary_name} ({status}) ==")
        typer.echo(
            f"  functions: {r.functions_inserted} inserted, "
            f"{r.functions_updated} updated "
            f"(placeholders created: {r.placeholders_created})"
        )
        typer.echo(
            f"  edges: {r.edges_inserted} inserted, {r.edges_skipped_duplicate} skipped (duplicate)"
        )
        if r.failures:
            typer.echo(f"  failures ({r.failure_count}):", err=True)
            for message in r.failures:
                typer.echo(f"    - {message}", err=True)
        else:
            typer.echo("  failures: none")

    total_failures = sum(r.failure_count for r in reports)
    total_functions = sum(r.total_functions for r in reports)
    typer.echo(
        f"\nDone: {len(reports)} binaries, {total_functions} functions, "
        f"{total_failures} per-item failures."
    )
