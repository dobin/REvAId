"""``/binaries/{id}/views`` routes — read-only listing (pulled forward from I6)."""

from __future__ import annotations

from fastapi import APIRouter

from graphrev.api.deps import SessionDep
from graphrev.schemas.view import ViewSummaryDto
from graphrev.services import view_service

router = APIRouter(tags=["views"])


@router.get("/binaries/{binary_id}/views", response_model=list[ViewSummaryDto])
async def list_binary_views(binary_id: int, session: SessionDep) -> list[ViewSummaryDto]:
    return await view_service.list_views_dto(session, binary_id)
