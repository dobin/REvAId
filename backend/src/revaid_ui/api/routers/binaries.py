"""Viewer-facing binary facade; all analysis facts come through HTTP."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, Request, status

from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_contracts.schemas.binary import BinarySummaryDto
from revaid_contracts.schemas.ingest import ImportJobAcceptedDto
from revaid_contracts.schemas.search import EntryPointDto, EntryPointsDto, FunctionSearchPageDto
from revaid_ui.api.deps import (
    AnalysisClientDep,
    SettingsDep,
    ViewerSessionDep,
    ViewerWriteSessionDep,
)
from revaid_ui.schemas.function import FunctionDto, function_dto_from_analysis
from revaid_ui.schemas.ingest import ImportJobStatusDto
from revaid_ui.services import binary_service

router = APIRouter(tags=["binaries"])
_SAFE_BINARY_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.()-]+$")


def _parse_address(raw: str) -> int:
    try:
        return int(raw, 16) if raw.lower().startswith("0x") else int(raw, 10)
    except ValueError as exc:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"Could not parse address '{raw}'.",
            details={"address": raw},
        ) from exc


@router.get("/binaries", response_model=list[BinarySummaryDto])
async def list_binaries(
    settings: SettingsDep, session: ViewerSessionDep, analysis: AnalysisClientDep
) -> list[BinarySummaryDto]:
    return await binary_service.list_binaries_from_analysis(
        analysis, session, redact_last_view=settings.public_mode
    )


async def _bounded_stream(request: Request, limit: int) -> AsyncIterator[bytes]:
    received = 0
    async for chunk in request.stream():
        received += len(chunk)
        if received > limit:
            raise AppError(
                ErrorCode.IMPORT_TOO_LARGE,
                "Upload exceeds the configured limit.",
                details={"maxBytes": limit},
            )
        yield chunk


@router.post("/binaries/import", response_model=ImportJobAcceptedDto, status_code=202)
async def import_binary(
    request: Request, settings: SettingsDep, analysis: AnalysisClientDep
) -> ImportJobAcceptedDto:
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    if content_type != "application/json":
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Import uploads must use Content-Type application/json.",
        )
    result = await analysis.import_upload(
        _bounded_stream(request, settings.import_max_upload_bytes),
        content_type=content_type,
    )
    return ImportJobAcceptedDto.model_validate(result)


@router.post("/binaries/decompile", response_model=ImportJobAcceptedDto, status_code=202)
async def decompile_binary(
    request: Request,
    settings: SettingsDep,
    analysis: AnalysisClientDep,
    name: str = Query(..., min_length=1, max_length=255),
    version: str = Query(default="", max_length=255),
) -> ImportJobAcceptedDto:
    if not _SAFE_BINARY_FILENAME_RE.fullmatch(name):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Binary filename must contain only ASCII letters, digits, hyphens, underscores, "
            "dots, and parentheses.",
            details={"name": name},
        )
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    if content_type != "application/octet-stream":
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Raw binary uploads must use Content-Type application/octet-stream.",
        )
    return ImportJobAcceptedDto.model_validate(
        await analysis.import_upload(
            _bounded_stream(request, settings.decompiler_max_upload_bytes),
            content_type=content_type,
            query={"name": name, "version": version},
        )
    )


@router.get("/binaries/imports/{job_id}", response_model=ImportJobStatusDto)
async def get_import_status(job_id: str, analysis: AnalysisClientDep) -> ImportJobStatusDto:
    return ImportJobStatusDto.model_validate(await analysis.get_import_status(job_id))


@router.delete("/binaries/imports/{job_id}", response_model=ImportJobStatusDto)
async def cancel_import(job_id: str, analysis: AnalysisClientDep) -> ImportJobStatusDto:
    return ImportJobStatusDto.model_validate(await analysis.cancel_import(job_id))


@router.delete("/binaries/{binary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_binary(
    binary_id: int,
    confirm: str,
    session: ViewerWriteSessionDep,
    analysis: AnalysisClientDep,
) -> None:
    await binary_service.delete_binary_via_analysis(
        analysis, session, binary_id=binary_id, confirm=confirm
    )


@router.get("/binaries/{binary_id}/entry-points", response_model=EntryPointsDto)
async def get_entry_points(binary_id: int, analysis: AnalysisClientDep) -> EntryPointsDto:
    rows = await analysis.get_entry_points(binary_id)
    return EntryPointsDto(
        entry_points=[
            EntryPointDto(
                id=row.id,
                address=row.address,
                display_name=row.display_name,
                fan_out=row.fan_out,
                fan_in=row.fan_in,
            )
            for row in rows
        ]
    )


@router.get("/binaries/{binary_id}/functions", response_model=FunctionSearchPageDto)
async def search_binary_functions(
    binary_id: int,
    settings: SettingsDep,
    analysis: AnalysisClientDep,
    q: str | None = Query(default=None),
    include_code: bool = Query(default=False),
    limit: int = Query(default=0, ge=0),
    offset: int = Query(default=0, ge=0),
) -> FunctionSearchPageDto:
    page_limit = min(
        limit or settings.function_search_default_limit,
        settings.function_search_max_limit,
    )
    return FunctionSearchPageDto.model_validate(
        await analysis.search_functions(binary_id, q, page_limit, offset, include_code)
    )


@router.get("/binaries/{binary_id}/functions/by-address", response_model=FunctionDto)
async def resolve_function_by_address(
    binary_id: int,
    analysis: AnalysisClientDep,
    address: str = Query(..., description="Hex (`0x...`) or decimal address."),
) -> FunctionDto:
    payload = await analysis.resolve_function_by_address(binary_id, _parse_address(address))
    return function_dto_from_analysis(payload)
