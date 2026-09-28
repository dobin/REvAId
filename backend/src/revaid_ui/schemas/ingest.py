"""Viewer-facing import job DTOs returned by analysis over HTTP."""

from __future__ import annotations

from pydantic import Field

from revaid_contracts.common import ApiModel


class ImportJobAcceptedDto(ApiModel):
    job_id: str
    phase: str
    bytes_received: int
    source_kind: str


class ImportJobStatusDto(ApiModel):
    job_id: str
    phase: str
    bytes_received: int
    source_kind: str
    result: dict[str, object] | None = None
    error_message: str | None = None
    error_code: str | None = None
    error_details: dict[str, object] | None = None
    failure_samples: list[str] = Field(default_factory=list)
