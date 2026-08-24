"""``/binaries`` routes (E1, E1a, E1b)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from graphrev.api.deps import SessionDep, SessionFactoryDep, SettingsDep
from graphrev.core.errors import AppError, ErrorCode
from graphrev.schemas.binary import BinarySummaryDto
from graphrev.schemas.function import FunctionDto
from graphrev.schemas.ingest import GhidraExportDocument, ImportResultDto
from graphrev.schemas.search import EntryPointsDto, FunctionSearchPageDto
from graphrev.services import binary_service, function_service, search_service

router = APIRouter(tags=["binaries"])


def _parse_address(raw: str) -> int:
    """Accept `0x...`/`0X...` hex or a bare decimal integer (D2)."""
    try:
        return int(raw, 16) if raw.lower().startswith("0x") else int(raw, 10)
    except ValueError as exc:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"Could not parse address '{raw}'.",
            details={"address": raw},
        ) from exc


@router.get("/binaries", response_model=list[BinarySummaryDto])
async def list_binaries(session: SessionDep) -> list[BinarySummaryDto]:
    return await binary_service.list_binaries_dto(session)


@router.post(
    "/binaries/import",
    response_model=ImportResultDto,
    status_code=status.HTTP_201_CREATED,
)
async def import_binary(
    document: GhidraExportDocument,
    session_factory: SessionFactoryDep,
    settings: SettingsDep,
) -> ImportResultDto:
    """Import a Ghidra JSON export as a binary (I12).

    Idempotent on `(name, version)` — re-importing upserts inherent fields and
    preserves analyst-owned data (A3).
    """
    return await binary_service.import_ghidra_export(session_factory, settings, document)


@router.delete("/binaries/{binary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_binary(binary_id: int, confirm: str, session: SessionDep) -> None:
    await binary_service.delete_binary_with_confirmation(
        session, binary_id=binary_id, confirm=confirm
    )


@router.get("/binaries/{binary_id}/entry-points", response_model=EntryPointsDto)
async def get_entry_points(binary_id: int, session: SessionDep) -> EntryPointsDto:
    return await binary_service.get_entry_points(session, binary_id)


@router.get("/binaries/{binary_id}/functions", response_model=FunctionSearchPageDto)
async def search_binary_functions(
    binary_id: int,
    session: SessionDep,
    settings: SettingsDep,
    q: str | None = Query(default=None, description="Substring filter (B11/E1a)."),
    limit: int = Query(default=0, ge=0),
    offset: int = Query(default=0, ge=0),
) -> FunctionSearchPageDto:
    effective_limit = limit or settings.function_search_default_limit
    return await search_service.search_functions_dto(
        session,
        settings,
        binary_id=binary_id,
        query=q,
        limit=effective_limit,
        offset=offset,
    )


@router.get("/binaries/{binary_id}/functions/by-address", response_model=FunctionDto)
async def resolve_function_by_address(
    binary_id: int,
    session: SessionDep,
    address: str = Query(..., description="Hex (`0x...`) or decimal address (D2)."),
) -> FunctionDto:
    parsed_address = _parse_address(address)
    return await function_service.resolve_by_address(
        session, binary_id=binary_id, address=parsed_address
    )
