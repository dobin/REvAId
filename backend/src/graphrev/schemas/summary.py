"""``/functions/{id}/summary*`` and ``/queue*`` DTOs (TAD §4.2 endpoints 17-21)."""

from __future__ import annotations

from pydantic import Field

from graphrev.schemas.common import ApiModel
from graphrev.summarization.queue import MAX_PRIORITY, MIN_PRIORITY


class SummaryDemandRequestDto(ApiModel):
    """``POST /functions/{id}/summary`` request body.

    ``reason`` is logging-only (card|table_row|detail|prefetch); it never
    affects queueing behaviour, only what shows up in structured logs.

    ``priority`` is bounded to `SummaryQueue`'s own
    [`MIN_PRIORITY`, `MAX_PRIORITY`] range at the DTO layer, so an
    out-of-range value fails FastAPI's 422 validation *before* any DB write
    happens — previously an out-of-range priority reached
    `services.summary_service.demand_summary`, whose own `queue.enqueue`
    raised `ValueError` (an unhandled 500) after the row had already been
    flipped to `summary_status='pending'`, stranding it there until the
    next boot's `recover_pending_summaries` sweep.
    """

    priority: int = Field(ge=MIN_PRIORITY, le=MAX_PRIORITY)
    reason: str | None = None


class SummaryDemandResponseDto(ApiModel):
    """``POST /functions/{id}/summary`` response — always one of:

    - **202** with ``summary_status="pending"`` and a ``queue_position``
      (C5a: this endpoint never blocks on the LLM).
    - **200** with the cached result already in ``summary_status="ready"``
      (C3: cache-first, no work scheduled).
    """

    function_id: int
    summary_status: str
    queue_position: int | None = None
    summary_short: str | None = None


class QueuedItemDto(ApiModel):
    function_id: int
    display_name: str
    priority: int


class InFlightItemDto(ApiModel):
    function_id: int
    display_name: str
    started_at: str | None = None


class QueueSnapshotDto(ApiModel):
    """``GET /queue`` (endpoint 20) — the chip's data source."""

    in_flight: list[InFlightItemDto]
    queued: list[QueuedItemDto]
    in_flight_count: int
    queued_count: int
    paused_until: str | None = None


class CancelPendingResponseDto(ApiModel):
    """``POST /queue/cancel-pending`` (endpoint 21) response."""

    cancelled_count: int
