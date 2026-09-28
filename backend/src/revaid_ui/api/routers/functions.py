"""Viewer function reads and analyst edits proxied to analysis service."""

from __future__ import annotations

from fastapi import APIRouter

from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_ui.api.deps import AnalysisClientDep
from revaid_ui.schemas.function import FunctionDto, FunctionUpdateDto

router = APIRouter(tags=["functions"])


def _function_dto(payload: dict[str, object]) -> dict[str, object]:
    summary_status = payload.get("summary_status", "none")
    return {
        **payload,
        "display_name": (
            payload.get("name_analyst") or payload.get("name_llm") or payload.get("name")
        ),
        "is_renamed": payload.get("name_analyst") is not None,
        "utility_source": "analyst" if payload.get("utility_override") is not None else "computed",
        "summary": {
            "status": summary_status,
            "short": payload.get("summary_short"),
            "long": payload.get("summary_long"),
            "model": payload.get("summary_model"),
            "adapter": payload.get("summary_adapter"),
            "error_code": payload.get("summary_error_code"),
            "low_confidence": payload.get("summary_low_confidence", False),
            "generated_at": payload.get("summary_generated_at"),
            "is_stale": summary_status == "stale",
            "isStale": summary_status == "stale",
        },
        "has_notes": bool(payload.get("notes")),
        "notes_updated_at": payload.get("notes_updated_at"),
        "callee_count": payload.get("fan_out", 0),
        "caller_count": payload.get("fan_in", 0),
    }


@router.get("/functions/{function_id}", response_model=FunctionDto)
async def get_function(function_id: int, analysis: AnalysisClientDep) -> FunctionDto:
    try:
        payload = await analysis.get_function_detail(function_id)
    except AppError as exc:
        if exc.http_status == 404 or exc.details == {"status": 404}:
            raise AppError(ErrorCode.FUNCTION_NOT_FOUND, f"No function {function_id}.") from exc
        raise
    return FunctionDto.model_validate(_function_dto(payload))


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
    return FunctionDto.model_validate(_function_dto(payload))
