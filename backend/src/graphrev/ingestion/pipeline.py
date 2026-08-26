"""Ingestion pipeline orchestration (A1, A3, A4, A7, A7a, B9, B17, F1b, F2).

`run_ingestion` is the single implementation shared by the CLI (`I2`) and,
eventually, incremental on-demand ingestion (A6) — the async pipeline reuses
the same repositories either way, so A3's idempotency rule has exactly one
implementation (TAD §1.3).

Transaction/failure model:
    * One `unit_of_work` transaction **per binary** — a failure ingesting one
        binary does not roll back another binary already committed in the same
        run.
    * Normal functions and edges use bounded multi-row UPSERT batches. A batch
        failure falls back to per-item SAVEPOINTs so A4 diagnostics remain
        best-effort without paying a SAVEPOINT for every healthy record.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graphrev.adapters.ghidra.base import GhidraAdapter, RawBinaryRef, RawEdge, RawFunction
from graphrev.core.config import Settings
from graphrev.core.logging import get_logger, log_event
from graphrev.db.models import Function, View
from graphrev.db.seed import create_default_view
from graphrev.db.uow import unit_of_work
from graphrev.ingestion.placeholders import placeholder_name
from graphrev.ingestion.report import BinaryIngestionReport
from graphrev.repositories.binaries import get_or_create_binary
from graphrev.repositories.edges import upsert_edge, upsert_edges_batch
from graphrev.repositories.functions import (
    FunctionBatchValues,
    recompute_fan_in_fan_out_and_utility,
    upsert_function,
    upsert_functions_batch,
)

logger = get_logger(__name__)

#: F1b bookkeeping key — must match `graphrev.db.startup._UTILITY_THRESHOLD_KEY`
#: exactly, so an API startup immediately after ingestion does not spuriously
#: re-trigger the F1b recompute for a threshold ingestion already applied.
_UTILITY_THRESHOLD_KEY = "utility_fanin_threshold"


def _batched[T](items: Iterator[T], size: int) -> Iterator[list[T]]:
    """Yield bounded groups without materialising an adapter's full output."""
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _function_values(raw_fn: RawFunction) -> FunctionBatchValues:
    return {
        "address": raw_fn.address,
        "name_ghidra": raw_fn.name,
        "parameters": [dict(p) for p in raw_fn.parameters],
        "signature": raw_fn.signature,
        "assembly": raw_fn.assembly,
        "code_c": raw_fn.code_c,
        "kind": raw_fn.kind,
        "has_indirect_calls": raw_fn.has_indirect_calls,
        "is_entry_point": raw_fn.is_entry_point,
    }


async def _ingest_one_binary(
    session: AsyncSession,
    adapter: GhidraAdapter,
    settings: Settings,
    binary_ref: RawBinaryRef,
    binary_source_path: str | None,
) -> BinaryIngestionReport:
    report = BinaryIngestionReport(binary_name=binary_ref.name)

    binary, _created = await get_or_create_binary(
        session, name=binary_ref.name, version=binary_ref.version, source_path=binary_source_path
    )

    # -- functions -------------------------------------------------------
    # The adapter may raise while yielding. Preserve the historic A4 behaviour
    # for that rare case while batching normal records below.
    function_iter = iter(adapter.iter_functions(binary_ref))
    function_batch: list[RawFunction] = []
    while True:
        try:
            raw_fn = next(function_iter)
        except StopIteration:
            break
        except Exception as exc:
            report.failures.append(f"function iteration error: {exc}")
            log_event(
                logger,
                "ingestion.function_failed",
                function_id=None,
                binary_id=binary.id,
                duration_ms=0,
                adapter="mock",
                model=None,
                outcome="error",
                error=str(exc),
            )
            continue
        function_batch.append(raw_fn)
        if len(function_batch) == settings.import_function_batch_size:
            await _ingest_function_batch(session, binary.id, function_batch, report)
            function_batch = []
    if function_batch:
        await _ingest_function_batch(session, binary.id, function_batch, report)

    # Address -> id lookup for edge resolution, built once after all
    # functions for this binary have been upserted.
    address_to_id = dict(
        (row.address, row.id)
        for row in (
            await session.execute(
                select(Function.address, Function.id).where(Function.binary_id == binary.id)
            )
        ).all()
    )

    # -- edges -------------------------------------------------------------
    edge_batches = _batched(iter(adapter.iter_edges(binary_ref)), settings.import_edge_batch_size)
    for edge_batch in edge_batches:
        await _ingest_edge_batch(session, binary.id, edge_batch, address_to_id, report)

    # -- A7a/F1b: fan_in/fan_out/is_utility, scoped to this binary ---------
    await recompute_fan_in_fan_out_and_utility(
        session, binary_id=binary.id, threshold=settings.utility_fanin_threshold
    )

    # -- B9: every binary must have at least one view ----------------------
    has_view = (
        await session.execute(select(View.id).where(View.binary_id == binary.id).limit(1))
    ).scalar_one_or_none()
    if has_view is None:
        await create_default_view(session, binary.id)

    return report


async def _ingest_function_batch(
    session: AsyncSession,
    binary_id: int,
    functions: list[RawFunction],
    report: BinaryIngestionReport,
) -> None:
    """Fast-path a healthy function batch, isolating only a failed batch."""
    try:
        _ids, inserted, updated = await upsert_functions_batch(
            session, binary_id=binary_id, functions=[_function_values(fn) for fn in functions]
        )
        report.functions_inserted += inserted
        report.functions_updated += updated
    except Exception:
        for raw_fn in functions:
            try:
                async with session.begin_nested():
                    _function_id, was_created = await upsert_function(
                        session,
                        binary_id=binary_id,
                        address=raw_fn.address,
                        name_ghidra=raw_fn.name,
                        parameters=[dict(p) for p in raw_fn.parameters],
                        signature=raw_fn.signature,
                        assembly=raw_fn.assembly,
                        code_c=raw_fn.code_c,
                        kind=raw_fn.kind,
                        has_indirect_calls=raw_fn.has_indirect_calls,
                        is_entry_point=raw_fn.is_entry_point,
                    )
                if was_created:
                    report.functions_inserted += 1
                else:
                    report.functions_updated += 1
            except Exception as exc:
                message = f"function 0x{raw_fn.address:x} ({raw_fn.name}): {exc}"
                report.failures.append(message)
                log_event(
                    logger,
                    "ingestion.function_failed",
                    function_id=None,
                    binary_id=binary_id,
                    duration_ms=0,
                    adapter="ghidra",
                    model=None,
                    outcome="error",
                    error=str(exc),
                )


async def _ingest_edge_batch(
    session: AsyncSession,
    binary_id: int,
    edges: list[RawEdge],
    address_to_id: dict[int, int],
    report: BinaryIngestionReport,
) -> None:
    """Resolve placeholders once per batch, then bulk-insert edges."""
    placeholders: dict[int, str | None] = {}
    for edge in edges:
        if edge.caller_address not in address_to_id:
            placeholders.setdefault(edge.caller_address, None)
        if edge.callee_address not in address_to_id:
            placeholders.setdefault(edge.callee_address, edge.callee_module)
    if placeholders:
        try:
            ids, inserted, _updated = await upsert_functions_batch(
                session,
                binary_id=binary_id,
                functions=[
                    FunctionBatchValues(
                        address=address,
                        name_ghidra=placeholder_name(address, module),
                        kind="placeholder",
                        placeholder_module=module,
                    )
                    for address, module in placeholders.items()
                ],
            )
            address_to_id.update(ids)
            report.placeholders_created += inserted
        except Exception:
            # The ordinary edge fallback below preserves best-effort handling.
            pass
    try:
        pairs = [
            (address_to_id[edge.caller_address], address_to_id[edge.callee_address])
            for edge in edges
        ]
        inserted, skipped = await upsert_edges_batch(session, binary_id=binary_id, edges=pairs)
        report.edges_inserted += inserted
        report.edges_skipped_duplicate += skipped
    except Exception:
        for edge in edges:
            try:
                caller_id = address_to_id[edge.caller_address]
                callee_id = address_to_id[edge.callee_address]
                async with session.begin_nested():
                    inserted = await upsert_edge(
                        session, binary_id=binary_id, caller_id=caller_id, callee_id=callee_id
                    )
                if inserted:
                    report.edges_inserted += 1
                else:
                    report.edges_skipped_duplicate += 1
            except Exception as exc:
                message = (
                    f"edge 0x{edge.caller_address:x} -> 0x{edge.callee_address:x}: {exc}"
                )
                report.failures.append(message)
                log_event(
                    logger,
                    "ingestion.edge_failed",
                    function_id=None,
                    binary_id=binary_id,
                    duration_ms=0,
                    adapter="ghidra",
                    model=None,
                    outcome="error",
                    error=str(exc),
                )


async def _write_utility_threshold_bookkeeping(session: AsyncSession, settings: Settings) -> None:
    """Keep `app_meta["utility_fanin_threshold"]` in sync with the threshold
    ingestion just applied, so `db.startup.recompute_utility_if_threshold_changed`
    does not immediately re-run a redundant recompute on next API startup."""
    from sqlalchemy import text

    await session.execute(
        text(
            "INSERT INTO app_meta (key, value) VALUES (:key, :value) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
        ),
        {"key": _UTILITY_THRESHOLD_KEY, "value": str(settings.utility_fanin_threshold)},
    )


async def run_ingestion(
    session_factory: async_sessionmaker[AsyncSession],
    adapter: GhidraAdapter,
    settings: Settings,
    *,
    binary_filter: str | None = None,
) -> list[BinaryIngestionReport]:
    """Ingest every binary the adapter reports (or just `binary_filter`, if given).

    One `unit_of_work` transaction per binary (commit-once-per-binary): a
    failure ingesting one binary is recorded and does not roll back another
    binary already committed in the same run.
    """
    reports: list[BinaryIngestionReport] = []
    binaries = adapter.list_binaries()
    if binary_filter is not None:
        binaries = [b for b in binaries if b.name == binary_filter]

    for raw_binary in binaries:
        binary_ref = RawBinaryRef(name=raw_binary.name, version=raw_binary.version)
        try:
            async with unit_of_work(session_factory) as session:
                report = await _ingest_one_binary(
                    session, adapter, settings, binary_ref, raw_binary.source_path
                )
                await _write_utility_threshold_bookkeeping(session, settings)
            reports.append(report)
        except Exception as exc:
            failed_report = BinaryIngestionReport(binary_name=raw_binary.name)
            failed_report.binary_failed = True
            failed_report.failures.append(f"binary-level failure: {exc}")
            log_event(
                logger,
                "ingestion.binary_failed",
                function_id=None,
                binary_id=None,
                duration_ms=0,
                adapter="mock",
                model=None,
                outcome="error",
                error=str(exc),
            )
            reports.append(failed_report)

    return reports
