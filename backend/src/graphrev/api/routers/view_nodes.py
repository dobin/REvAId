"""``PATCH /views/{id}/nodes`` — batch node upsert/remove (TAD §4.3 #12, I6)."""

from __future__ import annotations

from fastapi import APIRouter

from graphrev.api.deps import WriteSessionDep
from graphrev.schemas.view import (
    OpenFunctionsRequestDto,
    OpenFunctionsResponseDto,
    ViewNodesPatchRequestDto,
    ViewNodesPatchResponseDto,
)
from graphrev.services import canvas_service

router = APIRouter(tags=["view-nodes"])


@router.patch("/views/{view_id}/nodes", response_model=ViewNodesPatchResponseDto)
async def patch_view_nodes(
    view_id: int, request: ViewNodesPatchRequestDto, session: WriteSessionDep
) -> ViewNodesPatchResponseDto:
    nodes = await canvas_service.patch_view_nodes(session, view_id=view_id, request=request)
    return ViewNodesPatchResponseDto(nodes=nodes)


@router.post("/views/{view_id}/open-functions", response_model=OpenFunctionsResponseDto)
async def open_functions(
    view_id: int, request: OpenFunctionsRequestDto, session: WriteSessionDep
) -> OpenFunctionsResponseDto:
    return await canvas_service.open_functions(session, view_id=view_id, request=request)
