"""Service-independent error codes and envelope schema."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    BINARY_NOT_FOUND = "BINARY_NOT_FOUND"
    BINARY_ALREADY_EXISTS = "BINARY_ALREADY_EXISTS"
    FUNCTION_NOT_FOUND = "FUNCTION_NOT_FOUND"
    VIEW_NOT_FOUND = "VIEW_NOT_FOUND"
    ADDRESS_UNRESOLVED = "ADDRESS_UNRESOLVED"
    CONFIRMATION_MISMATCH = "CONFIRMATION_MISMATCH"
    SUMMARY_ALREADY_PENDING = "SUMMARY_ALREADY_PENDING"
    SUMMARY_PROVIDER_ERROR = "SUMMARY_PROVIDER_ERROR"
    SUMMARY_RATE_LIMITED = "SUMMARY_RATE_LIMITED"
    QUEUE_FULL = "QUEUE_FULL"
    IMPORT_TOO_LARGE = "IMPORT_TOO_LARGE"
    IMPORT_JOB_NOT_FOUND = "IMPORT_JOB_NOT_FOUND"
    DECOMPILER_UNAVAILABLE = "DECOMPILER_UNAVAILABLE"
    DECOMPILER_TIMEOUT = "DECOMPILER_TIMEOUT"
    DECOMPILER_FAILED = "DECOMPILER_FAILED"
    DECOMPILER_OUTPUT_TOO_LARGE = "DECOMPILER_OUTPUT_TOO_LARGE"
    ANALYSIS_UNAVAILABLE = "ANALYSIS_UNAVAILABLE"
    LAST_VIEW_DELETE_FORBIDDEN = "LAST_VIEW_DELETE_FORBIDDEN"
    PUBLIC_MODE_FORBIDDEN = "PUBLIC_MODE_FORBIDDEN"
    GHIDRA_PROGRAM_MISMATCH = "GHIDRA_PROGRAM_MISMATCH"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None

    @property
    def error_code(self) -> ErrorCode:
        return self.code

    @property
    def error_message(self) -> str:
        return self.message


class ErrorEnvelope(BaseModel):
    error: ErrorBody


__all__ = ["ErrorBody", "ErrorCode", "ErrorEnvelope"]
