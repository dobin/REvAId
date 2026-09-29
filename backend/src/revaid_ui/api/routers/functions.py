"""Viewer function reads and analyst edits proxied to analysis service."""

from __future__ import annotations

from fastapi import APIRouter, Query

from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_ui.api.deps import AnalysisClientDep
from revaid_ui.schemas.function import FunctionDto, FunctionUpdateDto, function_dto_from_analysis
from revaid_ui.schemas.function_data import FunctionDataDto, function_data_dto_from_analysis

router = APIRouter(tags=["functions"])


@router.get("/functions/{function_id}", response_model=FunctionDto)
async def get_function(function_id: int, analysis: AnalysisClientDep) -> FunctionDto:
    try:
        payload = await analysis.get_function_detail(function_id)
    except AppError as exc:
        if exc.http_status == 404 or exc.details == {"status": 404}:
            raise AppError(ErrorCode.FUNCTION_NOT_FOUND, f"No function {function_id}.") from exc
        raise
    return function_dto_from_analysis(payload)


@router.get("/functions/{function_id}/data", response_model=FunctionDataDto)
async def get_function_data(
    function_id: int,
    analysis: AnalysisClientDep,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> FunctionDataDto:
    try:
        payload = await analysis.get_function_data(function_id, limit, offset)
    except AppError as exc:
        if exc.http_status == 404 or exc.details == {"status": 404}:
            raise AppError(ErrorCode.FUNCTION_NOT_FOUND, f"No function {function_id}.") from exc
        raise
    return function_data_dto_from_analysis(payload)


@router.patch("/functions/{function_id}", response_model=FunctionDto)
async def update_function(
    function_id: int, update: FunctionUpdateDto, analysis: AnalysisClientDep
) -> FunctionDto:
    try:
        payload = await analysis.update_function(
            function_id, update.model_dump(exclude_unset=True, by_alias=False)
        )
    except AppError as exc:
        if exc.http_status == 404 or exc.details == {"status": 404}:
            raise AppError(ErrorCode.FUNCTION_NOT_FOUND, f"No function {function_id}.") from exc
        raise
    return function_dto_from_analysis(payload)
