"""Viewer summary-demand request DTO; response/queue DTOs live in ``revaid_contracts``."""

from __future__ import annotations

from pydantic import ConfigDict, Field

from revaid_contracts.analysis import MAX_SUMMARY_PRIORITY, MIN_SUMMARY_PRIORITY
from revaid_contracts.common import ApiModel


class SummaryDemandRequestDto(ApiModel):
    priority: int = Field(ge=MIN_SUMMARY_PRIORITY, le=MAX_SUMMARY_PRIORITY)
    reason: str | None = None

    model_config = ConfigDict(
        **ApiModel.model_config,
        extra="forbid",
    )
