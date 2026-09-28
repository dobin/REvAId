"""``/binaries/{id}/views`` and ``/views/{id}`` routes (TAD §4.2 #9-#11, I6).

ADR 0006 (public mode): the *shared* view-listing and last-view-pointer
endpoints are closed when `public_mode` is on — they would enumerate every
browser's view ids, defeating the capability model. By-id endpoints
(`GET/PATCH/DELETE /views/{id}`) stay open: the random id *is* the
credential.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_ui.api.deps import (
    AnalysisClientDep,
    SettingsDep,
    ViewerSessionDep,
    ViewerWriteSessionDep,
)
from revaid_ui.schemas.view import (
    SetLastViewRequestDto,
    ViewCreateDto,
    ViewDto,
    ViewPatchDto,
    ViewSummaryDto,
)
from revaid_ui.services import view_service

router = APIRouter(tags=["views"])


def _forbid_in_public_mode() -> None:
    raise AppError(
        ErrorCode.PUBLIC_MODE_FORBIDDEN,
        "View listing is disabled in public mode — anonymous views are "
        "tracked per browser and are not enumerable.",
        http_status=403,
    )


@router.get("/binaries/{binary_id}/views", response_model=list[ViewSummaryDto])
async def list_binary_views(
    binary_id: int,
    session: ViewerWriteSessionDep,
    settings: SettingsDep,
    analysis: AnalysisClientDep,
) -> list[ViewSummaryDto]:
    assert session is not None
    if settings.public_mode:
        _forbid_in_public_mode()
    return await view_service.list_views_dto(session, analysis, binary_id)


@router.post(
    "/binaries/{binary_id}/views", response_model=ViewDto, status_code=status.HTTP_201_CREATED
)
async def create_binary_view(
    binary_id: int,
    create: ViewCreateDto,
    session: ViewerWriteSessionDep,
    settings: SettingsDep,
    analysis: AnalysisClientDep,
) -> ViewDto:
    assert session is not None
    return await view_service.create_view_dto(
        session, analysis, binary_id, create, random_id=settings.public_mode
    )


@router.post("/binaries/{binary_id}/last-view", status_code=status.HTTP_204_NO_CONTENT)
async def set_last_view(
    binary_id: int,
    body: SetLastViewRequestDto,
    viewer_session: ViewerWriteSessionDep,
    settings: SettingsDep,
    analysis: AnalysisClientDep,
) -> None:
    assert viewer_session is not None
    if settings.public_mode:
        _forbid_in_public_mode()
    await view_service.set_last_view(
        analysis,
        viewer_session,
        binary_id=binary_id,
        view_id=body.view_id,
    )


@router.get("/views/{view_id}", response_model=ViewDto)
async def get_view(view_id: int, session: ViewerSessionDep) -> ViewDto:
    assert session is not None
    return await view_service.get_view_dto(session, view_id)


@router.patch("/views/{view_id}", response_model=ViewDto)
async def patch_view(
    view_id: int,
    patch: ViewPatchDto,
    session: ViewerWriteSessionDep,
    analysis: AnalysisClientDep,
) -> ViewDto:
    assert session is not None
    return await view_service.patch_view_dto(session, analysis, view_id, patch)


@router.delete("/views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_view(
    view_id: int,
    session: ViewerWriteSessionDep,
) -> None:
    assert session is not None
    await view_service.delete_view_dto(session, view_id)


@router.post(
    "/views/{view_id}/duplicate", response_model=ViewDto, status_code=status.HTTP_201_CREATED
)
async def duplicate_view(
    view_id: int, session: ViewerWriteSessionDep, settings: SettingsDep
) -> ViewDto:
    assert session is not None
    return await view_service.duplicate_view_dto(session, view_id, random_id=settings.public_mode)
