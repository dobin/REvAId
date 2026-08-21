"""Neighbour-table use case (D4-D7, D22, D23, D34, E2, E2a, E2b, E2c).

Side-effect free by construction (C2c/Q23): this module only reads via
`repositories.neighbours` and never touches `summary_status` or enqueues
anything — the summarization subsystem (I7/I9) does not exist yet, and even
once it does, nothing in this call chain is allowed to reach it.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.config import Settings
from graphrev.core.errors import AppError, ErrorCode
from graphrev.repositories.functions import get_function_by_id
from graphrev.repositories.neighbours import (
    Direction,
    Group,
    NeighbourRow,
    SortKey,
    SortOrder,
    fetch_neighbour_page,
)
from graphrev.schemas.neighbour import NeighbourPageDto, NeighbourRowDto


def _neighbour_row_dto(row: NeighbourRow) -> NeighbourRowDto:
    fn = row.function
    return NeighbourRowDto(
        id=fn.id,
        address=fn.address,
        display_name=fn.name_analyst or fn.name_ghidra,
        is_renamed=fn.name_analyst is not None,
        summary_short=fn.summary_short,
        summary_status=fn.summary_status,
        summary_low_confidence=fn.summary_low_confidence,
        kind=fn.kind,
        on_canvas=row.on_canvas,
        is_utility=fn.is_utility_effective,
        utility_source="analyst" if fn.utility_override is not None else "computed",
        fan_in=fn.fan_in,
        is_self=row.is_self,
        has_notes=fn.notes != "",
    )


async def get_neighbour_page(
    session: AsyncSession,
    settings: Settings,
    *,
    function_id: int,
    view_id: int,
    direction: Direction,
    group: Group,
    limit: int,
    offset: int,
    sort: SortKey,
    order: SortOrder,
    filter_text: str | None,
) -> NeighbourPageDto:
    fn = await get_function_by_id(session, function_id)
    if fn is None:
        raise AppError(
            ErrorCode.FUNCTION_NOT_FOUND,
            f"No function {function_id}.",
            details={"functionId": function_id},
        )

    result = await fetch_neighbour_page(
        session,
        function_id=function_id,
        view_id=view_id,
        direction=direction,
        group=group,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
        filter_text=filter_text,
        caller_suppress_threshold=settings.caller_suppress_threshold,
    )

    return NeighbourPageDto(
        function_id=function_id,
        direction=direction,
        group=group,
        rows=[_neighbour_row_dto(row) for row in result.rows],
        total=result.total,
        total_primary=result.total_primary,
        total_utility=result.total_utility,
        limit=limit,
        offset=offset,
        callers_suppressed=result.callers_suppressed,
        # §5.1 footer hint: only meaningful for the callees direction — a
        # function's own indirect-call gap can hide callees, never callers.
        may_be_incomplete=direction == "callees" and fn.has_indirect_calls,
    )
