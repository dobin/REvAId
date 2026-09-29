"""`graphrev ingest` command body (A1).

Extracted from `cli/__main__.py` so the Typer entry point stays a thin
options-parsing shim; this module owns the actual async orchestration, using
the same `create_engine`/`create_session_factory` CLI pattern as
`cli/dbtools.py`.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import shlex
from pathlib import Path

import typer

from revaid.adapters.ghidra import GhidraAdapterNotImplementedError, create_adapter
from revaid.core.config import GhidraAdapterName, Settings, get_settings
from revaid.db.engine import create_engine, create_session_factory, dispose_engine
from revaid.db.revision import MigrationNotAppliedError, read_revision, require_revision
from revaid.db.startup import ANALYSIS_MIGRATION_REVISION
from revaid.ingestion.pe_data.enrich import enrich_binary_with_pe_data
from revaid.ingestion.pipeline import run_ingestion
from revaid.ingestion.report import print_report
from revaid.ingestion.seed_summaries import seed_mock_summaries
from revaid.services.binary_service import import_ghidra_export, load_ghidra_export_file

_VALID_ADAPTER_NAMES: tuple[GhidraAdapterName, ...] = ("mock", "rest")


async def _check_analysis_database(settings: Settings) -> None:
    """Fail with setup guidance before an import touches an unmigrated DB."""
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        revision = await read_revision(session_factory, "Analysis")
        require_revision(revision, ANALYSIS_MIGRATION_REVISION, "Analysis")
    except MigrationNotAppliedError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    finally:
        await dispose_engine(engine)


def run(adapter: str, seed: int, binary: str | None) -> None:
    """Validate options, run ingestion, print the A4 report, exit non-zero
    if the adapter or analysis database could not be used; per-function and
    per-edge failures are reported, not fatal."""
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
        await _check_analysis_database(settings)
        engine = create_engine(settings)
        session_factory = create_session_factory(engine)
        try:
            reports = await run_ingestion(
                session_factory,
                ghidra_adapter,
                settings,
                binary_filter=binary,
            )
            if adapter == "mock":
                n = await seed_mock_summaries(session_factory)
                typer.echo(f"Seeded {n} mock summaries.")
        finally:
            await dispose_engine(engine)
        print_report(reports)
        if any(r.binary_failed for r in reports):
            raise typer.Exit(code=1)

    asyncio.run(_run())


def run_import(path: Path) -> None:
    """Import a supported analysis-export JSON file directly."""
    settings = get_settings()

    async def _run() -> None:
        await _check_analysis_database(settings)
        engine = create_engine(settings)
        session_factory = create_session_factory(engine)
        try:
            document = await load_ghidra_export_file(path)
            result = await import_ghidra_export(session_factory, settings, document)
        finally:
            await dispose_engine(engine)
        typer.echo(
            f"Imported {result.name} ({result.version}): "
            f"{result.functions_inserted} functions, {result.edges_inserted} edges."
        )
        if result.failures:
            typer.echo(f"{len(result.failures)} per-item failures.", err=True)

    asyncio.run(_run())


def run_decompile(path: Path, name: str | None, version: str) -> None:
    """Run the configured Kuna executable locally, then import its export."""
    binary_path = path.resolve()
    if not binary_path.is_file():
        typer.echo(f"Input binary does not exist: {binary_path}", err=True)
        raise typer.Exit(code=1)

    settings = get_settings()
    configured_executable = settings.decompiler_executable
    executable = str(Path(configured_executable).expanduser()) if configured_executable else None
    if executable is None or not Path(executable).is_file():
        typer.echo("Set GRAPHREV_DECOMPILER_EXECUTABLE to an executable Kuna path.", err=True)
        raise typer.Exit(code=1)

    async def _run() -> None:
        staging_dir = Path(settings.import_staging_dir).resolve()
        staging_dir.mkdir(parents=True, exist_ok=True)
        output_path = staging_dir / f"{os.urandom(16).hex()}.json"
        command = [
            executable,
            "decompile-graph",
            str(binary_path),
            "-o",
            str(output_path),
        ]
        command_text = shlex.join(command)
        try:
            await _check_analysis_database(settings)
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            output, _ = await asyncio.wait_for(
                process.communicate(), timeout=settings.decompiler_timeout_seconds
            )
            if process.returncode != 0:
                typer.echo(f"Kuna command: {command_text}", err=True)
                typer.echo(output.decode("utf-8", errors="replace"), err=True)
                raise typer.Exit(code=1)
            if not output_path.is_file() or output_path.stat().st_size == 0:
                typer.echo(
                    f"Kuna did not produce an analysis export. Command: {command_text}",
                    err=True,
                )
                if output:
                    typer.echo(output.decode("utf-8", errors="replace"), err=True)
                raise typer.Exit(code=1)

            document = await load_ghidra_export_file(output_path)
            digest = await asyncio.to_thread(_sha256_file, path)
            document = document.model_copy(
                update={
                    "binary": document.binary.model_copy(
                        update={
                            "name": name or path.name,
                            "version": version,
                            "source_path": str(path.resolve()),
                            "sha256": digest,
                        }
                    )
                }
            )
            engine = create_engine(settings)
            session_factory = create_session_factory(engine)
            try:
                result = await import_ghidra_export(session_factory, settings, document)
                pe_report = await enrich_binary_with_pe_data(
                    session_factory,
                    settings,
                    binary_name=result.name,
                    binary_version=result.version,
                    pe_path=path,
                )
            finally:
                await dispose_engine(engine)
            typer.echo(
                f"Analyzed and imported {result.name} ({result.version}): "
                f"{result.functions_inserted} functions, {result.edges_inserted} edges, "
                f"{pe_report.items_inserted} data items, {pe_report.refs_inserted} data references."
            )
            for warning in pe_report.warnings:
                typer.echo(f"Warning: {warning}", err=True)
        except TimeoutError as exc:
            typer.echo(f"Kuna analysis timed out. Command: {command_text}", err=True)
            raise typer.Exit(code=1) from exc
        except OSError as exc:
            typer.echo(f"Could not run Kuna. Command: {command_text}\n{exc}", err=True)
            raise typer.Exit(code=1) from exc
        finally:
            output_path.unlink(missing_ok=True)

    asyncio.run(_run())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
