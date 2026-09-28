"""Viewer composition for analysis neighbour pages and local canvas overlay."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from revaid_contracts.analysis import (
    AnalysisClient,
    Direction,
    Group,
    NeighbourQuery,
    SortKey,
    SortOrder,
)
from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_ui.core.config import Settings
from revaid_ui.repositories.view_nodes import list_visible_function_ids
from revaid_ui.repositories.views import get_view_by_id
from revaid_ui.schemas.neighbour import (
    NeighbourPageDto,
    NeighbourRowDto,
)


async def get_neighbour_page(
    session: AsyncSession,
    analysis: AnalysisClient,
    settings: Settings,
    *,
    function_id: int,
    view_id: int | None = None,
    direction: Direction,
    group: Group,
    limit: int,
    offset: int,
    sort: SortKey,
    order: SortOrder,
    filter_text: str | None,
) -> NeighbourPageDto:
    if sort == "callOrder" and direction != "callees":
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "callOrder sorting is only available for callees.",
            details={"direction": direction, "sort": sort},
        )
    result = await analysis.get_neighbours(
        NeighbourQuery(
            function_id=function_id,
            direction=direction,
            group=group,
            limit=limit,
            offset=offset,
            sort=sort,
            order=order,
            filter_text=filter_text,
            caller_suppress_threshold=settings.caller_suppress_threshold,
            table_row_cap=settings.table_row_cap,
        )
    )

    visible_ids: set[int] = set()
    if view_id is not None:
        view = await get_view_by_id(session, view_id)
        if view is not None and view.binary_id == result.binary_id:
            visible_ids = await list_visible_function_ids(
                session, view_id=view_id, function_ids=[row.id for row in result.rows]
            )

    return NeighbourPageDto(
        function_id=result.function_id,
        direction=direction,
        group=group,
        rows=[
            NeighbourRowDto(
                id=row.id,
                address=row.address,
                display_name=row.display_name,
                name_llm=row.name_llm,
                is_renamed=row.is_renamed,
                summary_short=row.summary_short,
                summary_status=row.summary_status,
                summary_low_confidence=row.summary_low_confidence,
                kind=row.kind,
                on_canvas=row.id in visible_ids,
                is_utility=row.is_utility,
                utility_source=row.utility_source,
                fan_in=row.fan_in,
                is_self=row.is_self,
                has_notes=row.has_notes,
                can_fan_out=row.can_fan_out,
            )
            for row in result.rows
        ],
        total=result.total,
        total_primary=result.total_primary,
        total_utility=result.total_utility,
        limit=result.limit,
        offset=result.offset,
        callers_suppressed=result.callers_suppressed,
        # §5.1 footer hint: only meaningful for the callees direction — a
        # function's own indirect-call gap can hide callees, never callers.
        may_be_incomplete=direction == "callees" and result.anchor_has_indirect_calls,
    )
