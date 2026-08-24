"""``/functions/{id}/summary*`` routes (TAD §4.2 endpoints 17-19, C2/C3/C7/C8)."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from graphrev.api.deps import EventBusDep, SessionDep, SummaryQueueDep
from graphrev.schemas.summary import SummaryDemandRequestDto, SummaryDemandResponseDto
from graphrev.services import summary_service

router = APIRouter(tags=["summaries"])


@router.post(
    "/functions/{function_id}/summary",
    response_model=SummaryDemandResponseDto,
)
async def demand_summary(
    function_id: int,
    request: SummaryDemandRequestDto,
    session: SessionDep,
    queue: SummaryQueueDep,
    event_bus: EventBusDep,
    response: Response,
) -> SummaryDemandResponseDto:
    """Demand a summary (endpoint 17). Returns **202** immediately if new
    work was scheduled (C5a — never blocks on the LLM), or **200** if a
    ready result was already cached (C3)."""
    result = await summary_service.demand_summary(
        session,
        queue,
        function_id=function_id,
        priority=request.priority,
        event_bus=event_bus,
    )
    response.status_code = (
        status.HTTP_200_OK if result.summary_status == "ready" else status.HTTP_202_ACCEPTED
    )
    return result


@router.delete(
    "/functions/{function_id}/summary",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def release_summary(
    function_id: int, queue: SummaryQueueDep, event_bus: EventBusDep
) -> None:
    """Release demand / cancel if unstarted (endpoint 18, C8). Advisory only
    — an in-flight generation is never interrupted."""
    summary_service.release_summary_demand(queue, function_id=function_id, event_bus=event_bus)


@router.delete(
    "/binaries/{binary_id}/summaries",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def clear_binary_summaries(
    binary_id: int, session: SessionDep, queue: SummaryQueueDep, event_bus: EventBusDep
) -> None:
    """TESTING affordance: wipe every LLM summary (`summary_short`/
    `summary_long` and friends) for all functions of the binary."""
    await summary_service.clear_binary_summaries(
        session, queue, binary_id=binary_id, event_bus=event_bus
    )


@router.post(
    "/functions/{function_id}/summary/regenerate",
    response_model=SummaryDemandResponseDto,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_summary(
    function_id: int, session: SessionDep, queue: SummaryQueueDep, event_bus: EventBusDep
) -> SummaryDemandResponseDto:
    """Force regeneration, bypassing the cache (endpoint 19, C7)."""
    return await summary_service.regenerate_summary(
        session, queue, function_id=function_id, event_bus=event_bus
    )
