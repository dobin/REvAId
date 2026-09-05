"""Binary use cases (E1): list, typed-confirm delete, entry-point suggestions,
and Ghidra JSON-export import (I12)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graphrev.adapters.ghidra import create_file_adapter
from graphrev.core.config import Settings
from graphrev.core.errors import AppError, ErrorCode
from graphrev.ingestion.pipeline import run_ingestion
from graphrev.repositories.binaries import (
    delete_binary,
    get_binary_by_id,
    get_binary_by_name_version,
    list_binaries,
)
from graphrev.repositories.functions import list_entry_points
from graphrev.schemas.binary import BinarySummaryDto, binary_summary_from_row
from graphrev.schemas.ingest import (
    SUPPORTED_EXPORT_SCHEMA_VERSIONS,
    GhidraExportDocument,
    ImportResultDto,
)
from graphrev.schemas.search import EntryPointDto, EntryPointsDto, entry_point_dto_from_function

#: E1b: "≤ 5 empty-canvas suggestions" — enforced server-side regardless of
#: whatever a caller might request, since there is no query parameter for it
#: in the TAD endpoint index.
_MAX_ENTRY_POINTS = 5


async def load_ghidra_export_file(path: Path) -> GhidraExportDocument:
    """Load one staged export without retaining HTTP request bytes.

    This is deliberately a compatibility bridge for the first streaming-upload
    slice. The following chunked-parser slice will replace this full-document
    decode; keeping it here makes that remaining memory limitation explicit
    and confines it to the background worker rather than the request handler.
    """

    def _load() -> GhidraExportDocument:
        with path.open(encoding="utf-8") as export_file:
            payload = json.load(export_file)
        return GhidraExportDocument.model_validate(payload)

    try:
        return await asyncio.to_thread(_load)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "The staged export is not a valid GraphRev Ghidra JSON document.",
            details={"reason": str(exc)},
        ) from exc


async def list_binaries_dto(
    session: AsyncSession, *, redact_last_view: bool = False
) -> list[BinarySummaryDto]:
    rows = await list_binaries(session)
    return [binary_summary_from_row(row, redact_last_view=redact_last_view) for row in rows]


async def delete_binary_with_confirmation(
    session: AsyncSession, *, binary_id: int, confirm: str
) -> None:
    """Typed-confirm destructive delete (E1).

    Raises `BINARY_NOT_FOUND` if `binary_id` does not exist, or
    `CONFIRMATION_MISMATCH` if `confirm` does not exactly match the binary's
    `name`. Cascade to functions/edges/views/view_nodes is handled entirely
    by the DB-level `ON DELETE CASCADE` foreign keys (see `db/models.py`).
    """
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )
    if confirm != binary.name:
        raise AppError(
            ErrorCode.CONFIRMATION_MISMATCH,
            "Confirmation text does not match the binary name.",
            details={"binaryId": binary_id, "expected": binary.name},
        )
    await delete_binary(session, binary)
    await session.commit()


async def get_entry_points(session: AsyncSession, binary_id: int) -> EntryPointsDto:
    """E1b: up to 5 entry-point suggestions for an empty canvas."""
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )
    functions = await list_entry_points(session, binary_id=binary_id, limit=_MAX_ENTRY_POINTS)
    entry_points: list[EntryPointDto] = [entry_point_dto_from_function(fn) for fn in functions]
    return EntryPointsDto(entry_points=entry_points)


async def import_ghidra_export(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    document: GhidraExportDocument,
) -> ImportResultDto:
    """Ingest a Ghidra JSON export as a binary (I12).

    Re-importing the same `(name, version)` is idempotent: the ingestion
    pipeline upserts inherent fields and preserves analyst-owned columns
    (`summary_*`, `name_analyst`, `notes`, `utility_override`) exactly as
    re-ingestion does (A3). Raises `VALIDATION_ERROR` for an unsupported
    schema version or if the pipeline reports the binary as failed.

    Takes the session *factory* rather than a request session because
    `run_ingestion` owns its own `unit_of_work` transactions (one per binary).
    """
    if document.schema_version not in SUPPORTED_EXPORT_SCHEMA_VERSIONS:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"Unsupported export schemaVersion {document.schema_version}; "
            f"this build supports {sorted(SUPPORTED_EXPORT_SCHEMA_VERSIONS)}.",
            details={
                "schemaVersion": document.schema_version,
                "supported": sorted(SUPPORTED_EXPORT_SCHEMA_VERSIONS),
            },
        )

    adapter = create_file_adapter(document)
    reports = await run_ingestion(
        session_factory, adapter, settings, binary_filter=document.binary.name
    )

    # `run_ingestion` yields one report; `binary_filter` restricts it to the
    # single binary this document carries.
    report = reports[0]
    if report.binary_failed:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"Ingestion of '{document.binary.name}' failed.",
            details={"failures": report.failures},
        )

    async with session_factory() as session:
        binary = await get_binary_by_name_version(
            session, name=document.binary.name, version=document.binary.version
        )
    if binary is None:  # pragma: no cover - defensive; ingestion just created it
        raise AppError(
            ErrorCode.INTERNAL_ERROR,
            f"Imported binary '{document.binary.name}' not found after ingestion.",
        )

    return ImportResultDto(
        binary_id=binary.id,
        name=binary.name,
        version=binary.version,
        functions_inserted=report.functions_inserted,
        functions_updated=report.functions_updated,
        edges_inserted=report.edges_inserted,
        placeholders_created=report.placeholders_created,
        failures=report.failures,
    )
