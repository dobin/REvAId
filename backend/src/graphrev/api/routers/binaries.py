"""``/binaries`` routes (E1, E1a, E1b)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query, Request, status

from graphrev.api.deps import ImportJobManagerDep, SessionDep, SettingsDep, WriteSessionDep
from graphrev.core.errors import AppError, ErrorCode
from graphrev.schemas.binary import BinarySummaryDto
from graphrev.schemas.function import FunctionDto
from graphrev.schemas.ingest import ImportJobAcceptedDto, ImportJobStatusDto
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
async def list_binaries(session: SessionDep, settings: SettingsDep) -> list[BinarySummaryDto]:
    # ADR 0006: `last_view_id` is a shared pointer across anonymous browsers;
    # redact it in public mode so the binary listing cannot leak which view
    # the owner last used.
    return await binary_service.list_binaries_dto(session, redact_last_view=settings.public_mode)


@router.post(
    "/binaries/import",
    response_model=ImportJobAcceptedDto,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_binary(
    request: Request,
    settings: SettingsDep,
    manager: ImportJobManagerDep,
) -> ImportJobAcceptedDto:
    """Stream a raw Ghidra JSON export to staging and enqueue its import.

    The configured byte cap is enforced during the read: Content-Length is
    merely an early rejection optimization because chunked requests lack it.
    """
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    if content_type != "application/json":
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Import uploads must use Content-Type application/json.",
        )
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > settings.import_max_upload_bytes:
                raise AppError(
                    ErrorCode.IMPORT_TOO_LARGE,
                    "Import exceeds the configured upload limit.",
                    details={"maxBytes": settings.import_max_upload_bytes},
                )
        except ValueError as exc:
            raise AppError(ErrorCode.VALIDATION_ERROR, "Invalid Content-Length header.") from exc

    path: Path = manager.staging_path()
    bytes_received = 0
    try:
        with path.open("xb") as staged_file:
            async for chunk in request.stream():
                bytes_received += len(chunk)
                if bytes_received > settings.import_max_upload_bytes:
                    raise AppError(
                        ErrorCode.IMPORT_TOO_LARGE,
                        "Import exceeds the configured upload limit.",
                        details={"maxBytes": settings.import_max_upload_bytes},
                    )
                staged_file.write(chunk)
        return await manager.submit(path, bytes_received=bytes_received)
    except Exception:
        path.unlink(missing_ok=True)
        raise


@router.get("/binaries/imports/{job_id}", response_model=ImportJobStatusDto)
async def get_import_status(job_id: str, manager: ImportJobManagerDep) -> ImportJobStatusDto:
    return manager.status(job_id)


@router.delete("/binaries/imports/{job_id}", response_model=ImportJobStatusDto)
async def cancel_import(job_id: str, manager: ImportJobManagerDep) -> ImportJobStatusDto:
    return manager.cancel(job_id)


@router.delete("/binaries/{binary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_binary(binary_id: int, confirm: str, session: WriteSessionDep) -> None:
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
