"""Import-job acceptance DTO returned by analysis and proxied by the viewer."""

from __future__ import annotations

from enum import StrEnum

from revaid_contracts.common import ApiModel

__all__ = ["ImportJobAcceptedDto", "ImportJobPhase"]


class ImportJobPhase(StrEnum):
    """Observable phases for a staged Ghidra import."""

    UPLOADING = "uploading"
    QUEUED = "queued"
    DECOMPILING = "decompiling"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImportJobAcceptedDto(ApiModel):
    """Returned as soon as a raw export has been staged safely."""

    job_id: str
    phase: ImportJobPhase
    bytes_received: int
    source_kind: str
