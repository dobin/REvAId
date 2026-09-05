"""Passive worker-outcome and explicit live-probe DTOs for the LLM sidebar."""

from __future__ import annotations

from typing import Literal

from graphrev.schemas.common import ApiModel

LlmWorkerOutcomeDto = Literal["success", "failure", "rate_limited", "no_outcome"]


class LlmStatusDto(ApiModel):
    """Last meaningful worker outcome for the currently configured LLM."""

    adapter: str
    model: str
    outcome: LlmWorkerOutcomeDto
    observed_at: str | None = None
    error_code: str | None = None


class LlmProbeDto(ApiModel):
    """Result of an explicitly requested, live adapter reachability probe."""

    reachable: bool
    detail: str | None = None