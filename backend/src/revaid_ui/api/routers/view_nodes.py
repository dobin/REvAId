"""``PATCH /views/{id}/nodes`` — batch node upsert/remove (TAD §4.3 #12, I6)."""

from __future__ import annotations

from fastapi import APIRouter

from revaid_ui.api.deps import AnalysisClientDep, ViewerWriteSessionDep
from revaid_ui.schemas.view import (
    OpenFunctionsRequestDto,
    OpenFunctionsResponseDto,
    ViewNodesPatchRequestDto,
    ViewNodesPatchResponseDto,
)
from revaid_ui.services import canvas_service

router = APIRouter(tags=["view-nodes"])


@router.patch("/views/{view_id}/nodes", response_model=ViewNodesPatchResponseDto)
async def patch_view_nodes(
    view_id: int,
    request: ViewNodesPatchRequestDto,
    session: ViewerWriteSessionDep,
    analysis: AnalysisClientDep,
) -> ViewNodesPatchResponseDto:
    assert session is not None
    nodes = await canvas_service.patch_view_nodes(
        session, analysis, view_id=view_id, request=request
    )
    return ViewNodesPatchResponseDto(nodes=nodes)


@router.post("/views/{view_id}/open-functions", response_model=OpenFunctionsResponseDto)
async def open_functions(
    view_id: int,
    request: OpenFunctionsRequestDto,
    session: ViewerWriteSessionDep,
    analysis: AnalysisClientDep,
) -> OpenFunctionsResponseDto:
    assert session is not None
    return await canvas_service.open_functions(session, analysis, view_id=view_id, request=request)
