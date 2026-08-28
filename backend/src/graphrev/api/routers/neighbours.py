"""``GET /functions/{id}/neighbours`` (E2, E2a, E2b) — TAD §4.3."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query

from graphrev.api.deps import SessionDep, SettingsDep
from graphrev.schemas.neighbour import NeighbourPageDto
from graphrev.services import neighbour_service

router = APIRouter(tags=["neighbours"])


@router.get("/functions/{function_id}/neighbours", response_model=NeighbourPageDto)
async def get_neighbours(
    function_id: int,
    session: SessionDep,
    settings: SettingsDep,
    view_id: int = Query(
        ..., alias="viewId", description="Required — on_canvas is a view fact (E2)."
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
    effective_limit = limit or settings.table_row_cap
    return await neighbour_service.get_neighbour_page(
        session,
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
