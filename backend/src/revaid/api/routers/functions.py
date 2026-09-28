"""``/functions`` routes (E1, E2c)."""

from __future__ import annotations

from fastapi import APIRouter

from revaid.api.deps import SessionDep, WriteSessionDep
from revaid.schemas.function import FunctionDto, FunctionUpdateDto
from revaid.services import function_service

router = APIRouter(tags=["functions"])


@router.get("/functions/{function_id}", response_model=FunctionDto)
async def get_function(
    function_id: int,
    session: SessionDep,
) -> FunctionDto:
    assert session is not None
    return await function_service.get_function(session, function_id)


@router.patch("/functions/{function_id}", response_model=FunctionDto)
async def update_function(
    function_id: int,
    update: FunctionUpdateDto,
    session: WriteSessionDep,
) -> FunctionDto:
    assert session is not None
    return await function_service.update_function(session, function_id, update)
