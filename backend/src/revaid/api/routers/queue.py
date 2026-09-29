"""``/queue`` routes (TAD §4.2 endpoints 20-21, E1c)."""

from __future__ import annotations

from fastapi import APIRouter

from revaid.api.deps import EventBusDep, SessionDep, SummaryQueueDep
from revaid.services import queue_service
from revaid_contracts.schemas.summary import CancelPendingResponseDto, QueueSnapshotDto

router = APIRouter(tags=["queue"])


@router.get("/queue", response_model=QueueSnapshotDto)
async def get_queue(
    session: SessionDep,
    queue: SummaryQueueDep,
) -> QueueSnapshotDto:
    """Queue snapshot for the chip (endpoint 20)."""
    assert session is not None and queue is not None
    return await queue_service.get_queue_snapshot(session, queue)


@router.post("/queue/cancel-pending", response_model=CancelPendingResponseDto)
async def cancel_pending(
    queue: SummaryQueueDep,
    event_bus: EventBusDep,
) -> CancelPendingResponseDto:
    """Drop all queued-unstarted items (endpoint 21)."""
    assert queue is not None and event_bus is not None
    return await queue_service.cancel_all_pending(queue, event_bus)
