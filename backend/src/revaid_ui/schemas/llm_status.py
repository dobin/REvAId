"""Viewer-facing LLM status responses from analysis."""

from __future__ import annotations

from typing import Literal

from revaid_contracts.common import ApiModel

LlmWorkerOutcomeDto = Literal["success", "failure", "rate_limited", "no_outcome"]


class LlmStatusDto(ApiModel):
    adapter: str
    model: str
    outcome: LlmWorkerOutcomeDto
    observed_at: str | None = None
    error_code: str | None = None


class LlmProbeDto(ApiModel):
    reachable: bool
    detail: str | None = None
