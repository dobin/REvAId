"""Viewer-facing queue and summary responses from the analysis service."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from revaid_contracts.analysis import MAX_SUMMARY_PRIORITY, MIN_SUMMARY_PRIORITY
from revaid_contracts.common import ApiModel


class QueuedItemDto(ApiModel):
    function_id: int
    display_name: str
    priority: int


class InFlightItemDto(ApiModel):
    function_id: int
    display_name: str
    started_at: str | None = None


class QueueSnapshotDto(ApiModel):
    in_flight: list[InFlightItemDto]
    queued: list[QueuedItemDto]
    in_flight_count: int
    queued_count: int
    paused_until: str | None = None


class CancelPendingResponseDto(ApiModel):
    cancelled_count: int


class SummaryDemandRequestDto(ApiModel):
    priority: int = Field(ge=MIN_SUMMARY_PRIORITY, le=MAX_SUMMARY_PRIORITY)
    reason: str | None = None

    model_config = ConfigDict(
        **ApiModel.model_config,
        extra="forbid",
    )


class SummaryDemandResponseDto(ApiModel):
    function_id: int
    summary_status: str
    queue_position: int | None = None
    summary_short: str | None = None
