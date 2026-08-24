"""``/functions/{id}/summary*`` and ``/queue*`` DTOs (TAD §4.2 endpoints 17-21)."""

from __future__ import annotations

from graphrev.schemas.common import ApiModel


class SummaryDemandRequestDto(ApiModel):
    """``POST /functions/{id}/summary`` request body.

    ``reason`` is logging-only (card|table_row|detail|prefetch); it never
    affects queueing behaviour, only what shows up in structured logs.
    """

    priority: int
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
