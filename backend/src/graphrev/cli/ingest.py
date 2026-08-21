"""`graphrev ingest` command body (A1).

Extracted from `cli/__main__.py` so the Typer entry point stays a thin
options-parsing shim; this module owns the actual async orchestration, using
the same `create_engine`/`create_session_factory` CLI pattern as
`cli/dbtools.py`.
"""

from __future__ import annotations

import asyncio

import typer

from graphrev.adapters.ghidra import GhidraAdapterNotImplementedError, create_adapter
from graphrev.core.config import GhidraAdapterName, get_settings
from graphrev.db.engine import create_engine, create_session_factory, dispose_engine
from graphrev.ingestion.pipeline import run_ingestion
from graphrev.ingestion.report import print_report

_VALID_ADAPTER_NAMES: tuple[GhidraAdapterName, ...] = ("mock", "rest")


def run(adapter: str, seed: int, binary: str | None) -> None:
    """Validate options, run ingestion, print the A4 report, exit non-zero
    only if the adapter itself could not be used (e.g. `--adapter rest`
    before M1) — per-function/per-edge failures are reported, not fatal."""
    if adapter not in _VALID_ADAPTER_NAMES:
        raise typer.BadParameter(
            f"--adapter must be one of {_VALID_ADAPTER_NAMES}, got {adapter!r}."
        )

    settings = get_settings()

    try:
        ghidra_adapter = create_adapter(adapter, seed=seed)
    except GhidraAdapterNotImplementedError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    async def _run() -> None:
        engine = create_engine(settings)
        session_factory = create_session_factory(engine)
        try:
            reports = await run_ingestion(
                session_factory, ghidra_adapter, settings, binary_filter=binary
            )
        finally:
            await dispose_engine(engine)
        print_report(reports)
        if any(r.binary_failed for r in reports):
            raise typer.Exit(code=1)

    asyncio.run(_run())
