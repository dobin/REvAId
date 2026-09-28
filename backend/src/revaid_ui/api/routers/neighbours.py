"""``GET /functions/{id}/neighbours`` (E2, E2a, E2b) — TAD §4.3."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_ui.api.deps import AnalysisClientDep, SettingsDep, ViewerSessionDep
from revaid_ui.schemas.neighbour import NeighbourPageDto
from revaid_ui.services import neighbour_service

router = APIRouter(tags=["neighbours"])


@router.get("/functions/{function_id}/neighbours", response_model=NeighbourPageDto)
async def get_neighbours(
    function_id: int,
    session: ViewerSessionDep,
    settings: SettingsDep,
    analysis: AnalysisClientDep,
    view_id: int | None = Query(
        default=None, alias="viewId", description="Optional viewer canvas overlay."
    ),
    direction: Literal["callees", "callers"] = Query(default="callees"),
    group: Literal["primary", "utility"] = Query(default="primary"),
    limit: int = Query(default=0, ge=0),
    offset: int = Query(default=0, ge=0),
    sort: Literal["callOrder", "name", "address", "fanIn"] | None = Query(default=None),
    order: Literal["asc", "desc"] = Query(default="asc"),
    filter: str | None = Query(
        default=None, description="Substring over name + summaryShort (D22)."
    ),
) -> NeighbourPageDto:
    assert session is not None
    if await analysis.get_function(function_id) is None:
        raise AppError(ErrorCode.FUNCTION_NOT_FOUND, f"No function {function_id}.")
    effective_limit = limit or settings.table_row_cap
    return await neighbour_service.get_neighbour_page(
        session,
        analysis,
        settings,
        function_id=function_id,
        view_id=view_id,
        direction=direction,
        group=group,
        limit=effective_limit,
        offset=offset,
        sort=sort or ("callOrder" if direction == "callees" else "name"),
        order=order,
        filter_text=filter,
    )
