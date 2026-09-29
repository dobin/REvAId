"""Viewer function reads and analyst edits proxied to analysis service."""

from __future__ import annotations

from fastapi import APIRouter

from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_ui.api.deps import AnalysisClientDep
from revaid_ui.schemas.function import FunctionDto, FunctionUpdateDto, function_dto_from_analysis

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
