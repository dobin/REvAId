"""Viewer proxies for analysis-owned summary controls."""

from __future__ import annotations

from contextlib import suppress

from fastapi import APIRouter, Response, status

from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_contracts.schemas.summary import SummaryDemandResponseDto
from revaid_ui.api.deps import AnalysisClientDep
from revaid_ui.schemas.summary import SummaryDemandRequestDto

router = APIRouter(tags=["summaries"])


@router.post(
    "/functions/{function_id}/summary",
    response_model=SummaryDemandResponseDto,
    status_code=status.HTTP_202_ACCEPTED,
)
async def demand_summary(
    function_id: int, request: SummaryDemandRequestDto, analysis: AnalysisClientDep
) -> SummaryDemandResponseDto:
    try:
        payload = await analysis.demand_summary(
            function_id, request.model_dump(exclude_unset=True, by_alias=False)
        )
    except AppError as exc:
        if exc.http_status == 404 or exc.details == {"status": 404}:
            raise AppError(ErrorCode.FUNCTION_NOT_FOUND, f"No function {function_id}.") from exc
        raise
    return SummaryDemandResponseDto.model_validate(payload)


@router.delete("/functions/{function_id}/summary", status_code=status.HTTP_204_NO_CONTENT)
async def release_summary(function_id: int, analysis: AnalysisClientDep) -> Response:
    with suppress(AppError):
        await analysis.release_summary(function_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/functions/{function_id}/summary/regenerate", status_code=202)
async def regenerate_summary(function_id: int, analysis: AnalysisClientDep) -> dict[str, object]:
    return await analysis.regenerate_summary(function_id)


@router.delete("/binaries/{binary_id}/summaries", status_code=status.HTTP_204_NO_CONTENT)
async def clear_binary_summaries(binary_id: int, analysis: AnalysisClientDep) -> Response:
    await analysis.clear_binary_summaries(binary_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
