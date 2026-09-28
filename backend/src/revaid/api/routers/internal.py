"""Fixed, versioned internal endpoints for the viewer-to-analysis boundary."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from revaid.api.deps import (
    EventBusDep,
    ImportJobManagerDep,
    LlmAdapterDep,
    SessionDep,
    SettingsDep,
    SummaryQueueDep,
    verify_internal_analysis_token,
)
from revaid.db.models import Edge, Function
from revaid.db.startup import ANALYSIS_MIGRATION_REVISION
from revaid.repositories.binaries import get_binary_by_id, list_binaries
from revaid.repositories.edges import find_canvas_origin
from revaid.repositories.functions import (
    get_function_address_bounds,
    list_entry_points,
    resolve_function_by_address,
    resolve_functions_by_addresses,
    search_functions,
)
from revaid.repositories.neighbours import fetch_neighbour_page
from revaid.schemas.config import app_config_from_settings
from revaid.schemas.function import FunctionUpdateDto, function_dto_from_row
from revaid.schemas.ingest import (
    GhidraExportDocument,
    ImportJobAcceptedDto,
    ImportJobStatusDto,
    ImportResultDto,
)
from revaid.schemas.llm_status import LlmProbeDto, LlmStatusDto
from revaid.schemas.search import function_search_row_from_function
from revaid.schemas.summary import (
    CancelPendingResponseDto,
    QueueSnapshotDto,
    SummaryDemandRequestDto,
    SummaryDemandResponseDto,
)
from revaid.services import function_service, llm_status_service, queue_service, summary_service
from revaid.services.binary_service import import_ghidra_export
from revaid.services.decompiler_health import check_decompiler_health
from revaid_contracts.analysis import (
    AddressResolution,
    AddressResolutionRequest,
    AddressResolutionResponse,
    AnalysisBinary,
    AnalysisFunction,
    CallPair,
    CanvasOrigin,
    CanvasOriginRequest,
    FeaturedFunction,
    FeaturedGraph,
    FunctionMembership,
    FunctionMembershipRequest,
    NeighbourItem,
    NeighbourPage,
    NeighbourQuery,
)
from revaid_contracts.http_errors import AppError, ErrorCode

router = APIRouter(
    prefix="/internal/v1",
    tags=["internal-analysis"],
    dependencies=[Depends(verify_internal_analysis_token)],
)

__all__ = ["router"]


@router.get("/health")
async def internal_health(session: SessionDep, settings: SettingsDep) -> dict[str, object]:
    assert session is not None
    await session.execute(select(1))
    reachable, detail = await check_decompiler_health(settings.decompiler_executable)
    return {
        "status": "ok",
        "decompiler_health": {"reachable": reachable, "detail": detail},
    }


@router.get("/config")
async def internal_config(settings: SettingsDep) -> dict[str, object]:
    return app_config_from_settings(settings).model_dump(mode="json", by_alias=True)


@router.get("/migration")
async def internal_migration_revision() -> dict[str, str]:
    return {"revision": ANALYSIS_MIGRATION_REVISION}


@router.get("/binaries")
async def internal_list_binaries(session: SessionDep) -> dict[str, list[dict[str, object]]]:
    assert session is not None
    rows = await list_binaries(session)
    return {
        "binaries": [
            {
                "id": row.binary.id,
                "name": row.binary.name,
                "version": row.binary.version,
                "analysis_image_base": row.binary.analysis_image_base,
                "address_min": None,
                "address_max": None,
                "function_count": row.function_count,
                "edge_count": row.edge_count,
                "created_at": row.binary.created_at,
            }
            for row in rows
        ]
    }


@router.get("/binaries/{binary_id}/entry-points")
async def internal_entry_points(binary_id: int, session: SessionDep) -> dict[str, object]:
    assert session is not None
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(ErrorCode.BINARY_NOT_FOUND, f"No binary {binary_id}.")
    functions = await list_entry_points(session, binary_id=binary_id, limit=5)
    return {
        "functions": [
            {
                "id": function.id,
                "binary_id": function.binary_id,
                "address": function.address,
                "display_name": function.name_analyst or function.name_llm or function.name,
                "name": function.name,
                "name_analyst": function.name_analyst,
                "name_llm": function.name_llm,
                "kind": function.kind,
                "placeholder_module": function.placeholder_module,
                "assembly": function.assembly,
                "code_c": function.code_c,
                "parameters": [],
                "signature": function.signature,
                "fan_in": function.fan_in,
                "fan_out": function.fan_out,
                "is_entry_point": function.is_entry_point,
                "is_featured": function.is_featured,
                "is_utility": function.is_utility_effective,
                "utility_override": function.utility_override,
                "summary_status": function.summary_status,
                "summary_short": function.summary_short,
                "summary_long": function.summary_long,
                "summary_low_confidence": function.summary_low_confidence,
                "notes": function.notes,
                "has_indirect_calls": function.has_indirect_calls,
            }
            for function in functions
        ]
    }


@router.get("/binaries/{binary_id}/functions")
async def internal_search_functions(
    binary_id: int,
    session: SessionDep,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    assert session is not None
    if not await get_binary_by_id(session, binary_id):
        raise AppError(ErrorCode.BINARY_NOT_FOUND, f"No binary {binary_id}.")
    limit = min(max(limit, 1), 200)
    functions, total = await search_functions(
        session, binary_id=binary_id, query=q, limit=limit, offset=max(offset, 0)
    )
    return {
        "rows": [
            function_search_row_from_function(function).model_dump(mode="json")
            for function in functions
        ],
        "total": total,
        "limit": limit,
        "offset": max(offset, 0),
        "query": q,
    }


@router.post("/binaries/{binary_id}/function-by-address")
async def internal_function_by_address(
    binary_id: int, body: dict[str, int], session: SessionDep
) -> dict[str, object]:
    assert session is not None
    function = await resolve_function_by_address(
        session, binary_id=binary_id, address=body["address"]
    )
    if function is None:
        raise AppError(ErrorCode.ADDRESS_UNRESOLVED, "No function contains that address.")
    return function_dto_from_row(function).model_dump(mode="json")


@router.delete("/binaries/{binary_id}", status_code=204)
async def internal_delete_binary(binary_id: int, body: dict[str, str], session: SessionDep) -> None:
    assert session is not None
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(ErrorCode.BINARY_NOT_FOUND, f"No binary {binary_id}.")
    if body.get("confirm") != binary.name:
        raise AppError(ErrorCode.CONFIRMATION_MISMATCH, "Confirmation text does not match.")
    from revaid.repositories.binaries import delete_binary

    await delete_binary(session, binary)
    await session.commit()


@router.post("/binaries/import-export", response_model=ImportResultDto)
async def internal_import_export(
    document: GhidraExportDocument,
    request: Request,
    settings: SettingsDep,
) -> ImportResultDto:
    assert hasattr(request.app.state, "session_factory")
    session_factory = request.app.state.session_factory
    return await import_ghidra_export(session_factory, settings, document)


@router.post("/import-upload", response_model=ImportJobAcceptedDto, status_code=202)
async def internal_import_upload(
    request: Request,
    settings: SettingsDep,
    manager: ImportJobManagerDep,
    name: str | None = Query(default=None, min_length=1, max_length=255),
    version: str = Query(default="", max_length=255),
) -> ImportJobAcceptedDto:
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    raw_binary = content_type == "application/octet-stream"
    if content_type != ("application/octet-stream" if raw_binary else "application/json"):
        raise AppError(ErrorCode.VALIDATION_ERROR, "Unsupported import upload content type.")
    if raw_binary:
        if name is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "Raw binary uploads require a name.")
        if not name or not all(
            character.isascii() and (character.isalnum() or character in "_.()-")
            for character in name
        ):
            raise AppError(ErrorCode.VALIDATION_ERROR, "Invalid raw binary filename.")
        maximum = settings.decompiler_max_upload_bytes
        suffix = ".bin"
        source_kind: Literal["json_export", "raw_binary"] = "raw_binary"
    else:
        maximum = settings.import_max_upload_bytes
        suffix = ".json"
        source_kind = "json_export"

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > maximum:
                raise AppError(
                    ErrorCode.IMPORT_TOO_LARGE,
                    "Import exceeds the configured upload limit.",
                    details={"maxBytes": maximum},
                )
        except ValueError as exc:
            raise AppError(ErrorCode.VALIDATION_ERROR, "Invalid Content-Length header.") from exc

    assert manager is not None
    path = manager.staging_path(suffix)
    bytes_received = 0
    try:
        with path.open("xb") as staged_file:
            async for chunk in request.stream():
                bytes_received += len(chunk)
                if bytes_received > maximum:
                    raise AppError(
                        ErrorCode.IMPORT_TOO_LARGE,
                        "Import exceeds the configured upload limit.",
                        details={"maxBytes": maximum},
                    )
                staged_file.write(chunk)
        return await manager.submit(
            path,
            bytes_received=bytes_received,
            source_kind=source_kind,
            binary_name=name,
            binary_version=version,
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise


@router.get("/imports/{job_id}", response_model=ImportJobStatusDto)
async def internal_import_status(job_id: str, manager: ImportJobManagerDep) -> ImportJobStatusDto:
    assert manager is not None
    return manager.status(job_id)


@router.delete("/imports/{job_id}", response_model=ImportJobStatusDto)
async def internal_cancel_import(job_id: str, manager: ImportJobManagerDep) -> ImportJobStatusDto:
    assert manager is not None
    return manager.cancel(job_id)


@router.get("/llm-status", response_model=LlmStatusDto)
async def internal_llm_status(session: SessionDep, settings: SettingsDep) -> LlmStatusDto:
    assert session is not None
    return await llm_status_service.get_passive_status(session, settings)


@router.post("/llm-status/probe", response_model=LlmProbeDto)
async def internal_llm_probe(adapter: LlmAdapterDep) -> LlmProbeDto:
    assert adapter is not None
    return await llm_status_service.probe(adapter)


@router.get("/queue", response_model=QueueSnapshotDto)
async def internal_queue(session: SessionDep, queue: SummaryQueueDep) -> QueueSnapshotDto:
    assert session is not None and queue is not None
    return await queue_service.get_queue_snapshot(session, queue)


@router.post("/queue/cancel-pending", response_model=CancelPendingResponseDto)
async def internal_cancel_pending(
    queue: SummaryQueueDep, event_bus: EventBusDep
) -> CancelPendingResponseDto:
    assert queue is not None and event_bus is not None
    return await queue_service.cancel_all_pending(queue, event_bus)


@router.post("/functions/{function_id}/summary", response_model=SummaryDemandResponseDto)
async def internal_demand_summary(
    function_id: int,
    body: SummaryDemandRequestDto,
    session: SessionDep,
    queue: SummaryQueueDep,
    event_bus: EventBusDep,
) -> SummaryDemandResponseDto:
    assert session is not None and queue is not None and event_bus is not None
    return await summary_service.demand_summary(
        session,
        queue,
        function_id=function_id,
        priority=body.priority,
        event_bus=event_bus,
    )


@router.delete("/functions/{function_id}/summary", status_code=204)
async def internal_release_summary(
    function_id: int, queue: SummaryQueueDep, event_bus: EventBusDep
) -> None:
    assert queue is not None and event_bus is not None
    summary_service.release_summary_demand(queue, function_id=function_id, event_bus=event_bus)


@router.post("/functions/{function_id}/summary/regenerate", response_model=SummaryDemandResponseDto)
async def internal_regenerate_summary(
    function_id: int,
    session: SessionDep,
    queue: SummaryQueueDep,
    event_bus: EventBusDep,
) -> SummaryDemandResponseDto:
    assert session is not None and queue is not None and event_bus is not None
    return await summary_service.regenerate_summary(
        session, queue, function_id=function_id, event_bus=event_bus
    )


@router.delete("/binaries/{binary_id}/summaries", status_code=204)
async def internal_clear_summaries(
    binary_id: int, session: SessionDep, queue: SummaryQueueDep, event_bus: EventBusDep
) -> None:
    assert session is not None and queue is not None and event_bus is not None
    await summary_service.clear_binary_summaries(
        session, queue, binary_id=binary_id, event_bus=event_bus
    )


@router.get("/functions/{function_id}", response_model=AnalysisFunction)
async def get_analysis_function(function_id: int, session: SessionDep) -> AnalysisFunction:
    function = await session.get(Function, function_id)
    if function is None:
        raise AppError(ErrorCode.FUNCTION_NOT_FOUND, f"No function {function_id}.")
    dto = function_dto_from_row(function)
    return AnalysisFunction(
        id=dto.id,
        binary_id=dto.binary_id,
        address=dto.address,
        display_name=dto.display_name,
        name=dto.name,
        name_analyst=dto.name_analyst,
        name_llm=dto.name_llm,
        kind=dto.kind,
        placeholder_module=function.placeholder_module,
        assembly=dto.assembly,
        code_c=dto.code_c,
        parameters=[param.model_dump() for param in dto.parameters],
        signature=dto.signature,
        fan_in=dto.fan_in,
        fan_out=dto.fan_out,
        is_entry_point=dto.is_entry_point,
        is_featured=function.is_featured,
        is_utility=dto.is_utility,
        utility_override=dto.utility_override,
        summary_status=dto.summary.status,
        summary_short=dto.summary.short,
        summary_long=dto.summary.long,
        summary_model=dto.summary.model,
        summary_adapter=dto.summary.adapter,
        summary_error_code=dto.summary.error_code,
        summary_low_confidence=dto.summary.low_confidence,
        summary_generated_at=dto.summary.generated_at,
        notes=dto.notes,
        notes_updated_at=dto.notes_updated_at,
        has_indirect_calls=dto.has_indirect_calls,
    )


@router.patch("/functions/{function_id}")
async def internal_update_function(
    function_id: int, update: FunctionUpdateDto, session: SessionDep
) -> dict[str, object]:
    assert session is not None
    result = await function_service.update_function(session, function_id, update)
    return result.model_dump(mode="json", by_alias=False)


@router.get("/binaries/{binary_id}", response_model=AnalysisBinary)
async def get_analysis_binary(binary_id: int, session: SessionDep) -> AnalysisBinary:
    assert session is not None
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(ErrorCode.BINARY_NOT_FOUND, f"No binary {binary_id}.")
    bounds = await get_function_address_bounds(session, binary_id=binary_id)
    return AnalysisBinary(
        id=binary.id,
        name=binary.name,
        version=binary.version,
        analysis_image_base=binary.analysis_image_base,
        address_min=bounds[0] if bounds else None,
        address_max=bounds[1] if bounds else None,
    )


@router.post("/binaries/{binary_id}/functions/membership", response_model=FunctionMembership)
async def get_function_membership(
    binary_id: int, body: FunctionMembershipRequest, session: SessionDep
) -> FunctionMembership:
    assert session is not None
    if not await get_binary_by_id(session, binary_id):
        raise AppError(ErrorCode.BINARY_NOT_FOUND, f"No binary {binary_id}.")
    if len(body.function_ids) > 500:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "At most 500 function IDs can be checked in one request.",
        )
    if not body.function_ids:
        return FunctionMembership(valid_ids=[])
    rows = await session.execute(
        select(Function.id).where(
            Function.binary_id == binary_id, Function.id.in_(set(body.function_ids))
        )
    )
    return FunctionMembership(valid_ids=sorted(rows.scalars().all()))


@router.post("/binaries/{binary_id}/functions/resolve", response_model=AddressResolutionResponse)
async def resolve_function_addresses(
    binary_id: int, body: AddressResolutionRequest, session: SessionDep
) -> AddressResolutionResponse:
    assert session is not None
    if not await get_binary_by_id(session, binary_id):
        raise AppError(ErrorCode.BINARY_NOT_FOUND, f"No binary {binary_id}.")
    if len(body.addresses) > 500:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "At most 500 addresses can be resolved in one request.",
        )
    functions_by_address = await resolve_functions_by_addresses(
        session, binary_id=binary_id, addresses=body.addresses
    )
    resolved: list[AddressResolution] = []
    for address in body.addresses:
        function = functions_by_address.get(address)
        exact = function if function is not None and function.address == address else None
        resolved.append(
            AddressResolution(
                address=address,
                function=(
                    None
                    if exact is None
                    else {
                        "id": exact.id,
                        "binary_id": exact.binary_id,
                        "address": exact.address,
                        "display_name": exact.name_analyst or exact.name_llm or exact.name,
                        "kind": exact.kind,
                        "placeholder_module": exact.placeholder_module,
                        "assembly": exact.assembly,
                        "code_c": exact.code_c,
                    }
                ),
                containing_function=(
                    None
                    if function is None
                    else {
                        "id": function.id,
                        "binary_id": function.binary_id,
                        "address": function.address,
                        "display_name": function.name_analyst or function.name_llm or function.name,
                        "kind": function.kind,
                        "placeholder_module": function.placeholder_module,
                        "assembly": function.assembly,
                        "code_c": function.code_c,
                    }
                ),
            )
        )
    return AddressResolutionResponse(results=resolved)


@router.get("/binaries/{binary_id}/featured-graph", response_model=FeaturedGraph)
async def get_featured_graph(binary_id: int, session: SessionDep) -> FeaturedGraph:
    assert session is not None
    if not await get_binary_by_id(session, binary_id):
        raise AppError(ErrorCode.BINARY_NOT_FOUND, f"No binary {binary_id}.")
    ids = list(
        (
            await session.execute(
                select(Function.id)
                .where(Function.binary_id == binary_id, Function.is_featured.is_(True))
                .order_by(Function.address, Function.id)
            )
        ).scalars()
    )
    calls = []
    if ids:
        pairs = (
            await session.execute(
                select(Edge.caller_id, Edge.callee_id).where(
                    Edge.binary_id == binary_id,
                    Edge.kind == "call",
                    Edge.caller_id.in_(ids),
                    Edge.callee_id.in_(ids),
                )
            )
        ).all()
        calls = [CallPair(caller_id=caller, callee_id=callee) for caller, callee in pairs]
    return FeaturedGraph(functions=[FeaturedFunction(id=id_) for id_ in ids], calls=calls)


@router.post("/functions/canvas-origin", response_model=CanvasOrigin)
async def get_canvas_origin(body: CanvasOriginRequest, session: SessionDep) -> CanvasOrigin:
    assert session is not None
    if len(body.candidate_ids) > 499:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "At most 499 canvas-origin candidates can be checked in one request.",
        )
    candidate_ids = set(body.candidate_ids)
    membership = await get_function_membership(
        body.binary_id,
        FunctionMembershipRequest(function_ids=[body.function_id, *candidate_ids]),
        session,
    )
    valid_ids = set(membership.valid_ids)
    if body.function_id not in valid_ids or candidate_ids - valid_ids:
        raise AppError(
            ErrorCode.FUNCTION_NOT_FOUND,
            "Canvas-origin functions must belong to the requested binary.",
        )
    origin = await find_canvas_origin(
        session, function_id=body.function_id, candidate_ids=candidate_ids
    )
    return CanvasOrigin(
        function_id=body.function_id,
        origin_function_id=origin[0] if origin else None,
        origin_kind=origin[1] if origin else "root",
    )


@router.post("/neighbours", response_model=NeighbourPage)
async def get_neighbours_internal(body: NeighbourQuery, session: SessionDep) -> NeighbourPage:
    assert session is not None
    result = await fetch_neighbour_page(
        session,
        function_id=body.function_id,
        direction=body.direction,
        group=body.group,
        limit=min(body.limit, body.table_row_cap),
        offset=body.offset,
        sort=body.sort,
        order=body.order,
        filter_text=body.filter_text,
        caller_suppress_threshold=body.caller_suppress_threshold,
    )
    anchor = await session.get(Function, body.function_id)
    if anchor is None:
        raise AppError(ErrorCode.FUNCTION_NOT_FOUND, f"No function {body.function_id}.")
    rows = [
        NeighbourItem(
            id=row.function.id,
            address=row.function.address,
            display_name=row.function.name_analyst or row.function.name_llm or row.function.name,
            name_llm=row.function.name_llm,
            is_renamed=row.function.name_analyst is not None,
            summary_short=row.function.summary_short,
            summary_status=row.function.summary_status,
            summary_low_confidence=row.function.summary_low_confidence,
            kind=row.function.kind,
            is_utility=row.function.is_utility_effective,
            utility_source="analyst" if row.function.utility_override is not None else "computed",
            fan_in=row.function.fan_in,
            is_self=row.is_self,
            has_notes=row.function.notes != "",
            can_fan_out=row.function.placeholder_module is None
            and (row.function.assembly is not None or row.function.code_c is not None),
        )
        for row in result.rows
    ]
    return NeighbourPage(
        function_id=body.function_id,
        binary_id=anchor.binary_id,
        anchor_has_indirect_calls=anchor.has_indirect_calls,
        direction=body.direction,
        group=body.group,
        rows=rows,
        total=result.total,
        total_primary=result.total_primary,
        total_utility=result.total_utility,
        limit=body.limit,
        offset=body.offset,
        callers_suppressed=result.callers_suppressed,
        may_be_incomplete=body.direction == "callees" and anchor.has_indirect_calls,
    )
