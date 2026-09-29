"""Post-import enrichment: persist PE data items and function -> data references."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revaid.core.config import Settings
from revaid.db.models import Binary, Function
from revaid.db.uow import unit_of_work
from revaid.ingestion.pe_data.extract import ExtractionResult, extract_data_references
from revaid.ingestion.pe_data.pe_image import PeImage
from revaid.repositories.data_items import DataItemValues, DataRefValues, replace_binary_data
from revaid_contracts.logging import get_logger, log_event

logger = get_logger(__name__)

_FUNCTION_PAGE = 500


@dataclass(slots=True)
class PeDataReport:
    items_inserted: int = 0
    refs_inserted: int = 0
    warnings: list[str] = field(default_factory=list)


async def enrich_binary_with_pe_data(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    binary_name: str,
    binary_version: str,
    pe_path: Path,
) -> PeDataReport:
    """Extract and store data items for an imported binary. Never raises.

    Failures (not a PE, damaged file, unexpected error) become warnings; the
    already committed import is unaffected.
    """
    report = PeDataReport()
    if not settings.pe_data_enabled:
        return report
    try:
        image = await asyncio.to_thread(PeImage, pe_path)
    except Exception as exc:
        report.warnings.append(f"PE data extraction skipped: cannot parse PE ({exc}).")
        log_event(logger, "pe_data.parse_failed", error=str(exc))
        return report

    try:
        async with session_factory() as session:
            binary = await session.scalar(
                select(Binary).where(Binary.name == binary_name, Binary.version == binary_version)
            )
            if binary is None:
                report.warnings.append("PE data extraction skipped: imported binary not found.")
                return report
            binary_id = binary.id
            image_base = binary.analysis_image_base
            rows = await _load_function_assembly(session, binary_id)

        result = await asyncio.to_thread(
            extract_data_references,
            image,
            rows,
            analysis_image_base=image_base,
            preview_bytes=settings.pe_data_preview_bytes,
            max_string_bytes=settings.pe_data_max_string_bytes,
            max_items=settings.pe_data_max_items,
        )
        if result.truncated:
            report.warnings.append(
                f"PE data items truncated at {settings.pe_data_max_items} items."
            )
        await _persist(session_factory, binary_id, result, report)
    except Exception as exc:
        report.warnings.append(f"PE data extraction failed: {exc}")
        log_event(logger, "pe_data.failed", error=str(exc))
    return report


async def _load_function_assembly(
    session: AsyncSession, binary_id: int
) -> list[tuple[int, int, str | None]]:
    rows: list[tuple[int, int, str | None]] = []
    last_id = 0
    while True:
        page = (
            await session.execute(
                select(Function.id, Function.address, Function.assembly)
                .where(
                    Function.binary_id == binary_id,
                    Function.id > last_id,
                    Function.assembly.is_not(None),
                )
                .order_by(Function.id)
                .limit(_FUNCTION_PAGE)
            )
        ).all()
        if not page:
            return rows
        rows.extend((fid, addr, asm) for fid, addr, asm in page)
        last_id = page[-1][0]


async def _persist(
    session_factory: async_sessionmaker[AsyncSession],
    binary_id: int,
    result: ExtractionResult,
    report: PeDataReport,
) -> None:
    items = [
        DataItemValues(
            address=i.address,
            rva=i.rva,
            section=i.section,
            kind=i.kind,
            size=i.size,
            value_text=i.value_text,
            target_address=i.target_address,
            preview_hex=i.preview_hex,
            is_writable=i.is_writable,
        )
        for i in result.items.values()
    ]
    refs = [
        DataRefValues(
            function_id=r.function_id,
            item_address=r.item_address,
            instruction_address=r.instruction_address,
            instruction_text=r.instruction_text,
        )
        for r in result.refs
    ]
    async with unit_of_work(session_factory) as session:
        # Inserts are executemany-style (list of dicts), so they are not bound
        # by SQLite's per-statement variable limit.
        report.items_inserted, report.refs_inserted = await replace_binary_data(
            session, binary_id=binary_id, items=items, refs=refs
        )
