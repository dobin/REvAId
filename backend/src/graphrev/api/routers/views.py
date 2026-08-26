"""``/binaries/{id}/views`` and ``/views/{id}`` routes (TAD §4.2 #9-#11, I6)."""

from __future__ import annotations

from fastapi import APIRouter, status

from graphrev.api.deps import SessionDep, WriteSessionDep
from graphrev.schemas.view import (
    SetLastViewRequestDto,
    ViewCreateDto,
    ViewDto,
    ViewPatchDto,
    ViewSummaryDto,
)
from graphrev.services import view_service

router = APIRouter(tags=["views"])


@router.get("/binaries/{binary_id}/views", response_model=list[ViewSummaryDto])
async def list_binary_views(binary_id: int, session: SessionDep) -> list[ViewSummaryDto]:
    return await view_service.list_views_dto(session, binary_id)


@router.post(
    "/binaries/{binary_id}/views", response_model=ViewDto, status_code=status.HTTP_201_CREATED
)
async def create_binary_view(
    binary_id: int, create: ViewCreateDto, session: WriteSessionDep
) -> ViewDto:
    return await view_service.create_view_dto(session, binary_id, create)


@router.post("/binaries/{binary_id}/last-view", status_code=status.HTTP_204_NO_CONTENT)
async def set_last_view(
    binary_id: int, body: SetLastViewRequestDto, session: WriteSessionDep
) -> None:
    await view_service.set_last_view(session, binary_id=binary_id, view_id=body.view_id)


@router.get("/views/{view_id}", response_model=ViewDto)
async def get_view(view_id: int, session: SessionDep) -> ViewDto:
    return await view_service.get_view_dto(session, view_id)


@router.patch("/views/{view_id}", response_model=ViewDto)
async def patch_view(view_id: int, patch: ViewPatchDto, session: WriteSessionDep) -> ViewDto:
    return await view_service.patch_view_dto(session, view_id, patch)


@router.delete("/views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_view(view_id: int, session: WriteSessionDep) -> None:
    await view_service.delete_view_dto(session, view_id)


@router.post(
    "/views/{view_id}/duplicate", response_model=ViewDto, status_code=status.HTTP_201_CREATED
)
async def duplicate_view(view_id: int, session: WriteSessionDep) -> ViewDto:
    return await view_service.duplicate_view_dto(session, view_id)
