"""``/queue`` routes (TAD §4.2 endpoints 20-21, E1c)."""

from __future__ import annotations

from fastapi import APIRouter

from revaid_contracts.schemas.summary import CancelPendingResponseDto, QueueSnapshotDto
from revaid_ui.api.deps import AnalysisClientDep

router = APIRouter(tags=["queue"])


@router.get("/queue", response_model=QueueSnapshotDto)
async def get_queue(
    analysis: AnalysisClientDep,
) -> QueueSnapshotDto:
    """Queue snapshot for the chip (endpoint 20)."""
    return QueueSnapshotDto.model_validate(await analysis.get_queue())


@router.post("/queue/cancel-pending", response_model=CancelPendingResponseDto)
async def cancel_pending(
    analysis: AnalysisClientDep,
) -> CancelPendingResponseDto:
    """Drop all queued-unstarted items (endpoint 21)."""
    result = await analysis.cancel_pending()
    return CancelPendingResponseDto.model_validate(result)
