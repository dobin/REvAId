"""``/functions`` routes (E1)."""

from __future__ import annotations

from fastapi import APIRouter

from graphrev.api.deps import SessionDep
from graphrev.schemas.function import FunctionDto
from graphrev.services import function_service

router = APIRouter(tags=["functions"])


@router.get("/functions/{function_id}", response_model=FunctionDto)
async def get_function(function_id: int, session: SessionDep) -> FunctionDto:
    return await function_service.get_function(session, function_id)
