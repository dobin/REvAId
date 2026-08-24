"""``/queue`` routes (TAD §4.2 endpoints 20-21, E1c)."""

from __future__ import annotations

from fastapi import APIRouter

from graphrev.api.deps import EventBusDep, SessionDep, SummaryQueueDep
from graphrev.schemas.summary import CancelPendingResponseDto, QueueSnapshotDto
from graphrev.services import queue_service

router = APIRouter(tags=["queue"])


@router.get("/queue", response_model=QueueSnapshotDto)
async def get_queue(session: SessionDep, queue: SummaryQueueDep) -> QueueSnapshotDto:
    """Queue snapshot for the chip (endpoint 20)."""
    return await queue_service.get_queue_snapshot(session, queue)


@router.post("/queue/cancel-pending", response_model=CancelPendingResponseDto)
async def cancel_pending(queue: SummaryQueueDep, event_bus: EventBusDep) -> CancelPendingResponseDto:
    """Drop all queued-unstarted items (endpoint 21)."""
    return await queue_service.cancel_all_pending(queue, event_bus)
