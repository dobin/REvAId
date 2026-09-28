"""Structured error envelope and machine-readable error codes (E4).

The PRD only requires "structured errors with machine-readable codes" — the
envelope shape and this specific code list are TAD/implementation decisions
(TAD §4.1), unconstrained by the PRD.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from revaid_contracts.errors import ErrorBody, ErrorCode, ErrorEnvelope

#: Default HTTP status per error code. Routers may override per-raise.
_DEFAULT_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.BINARY_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.BINARY_ALREADY_EXISTS: status.HTTP_409_CONFLICT,
    ErrorCode.FUNCTION_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.VIEW_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.ADDRESS_UNRESOLVED: status.HTTP_404_NOT_FOUND,
    ErrorCode.CONFIRMATION_MISMATCH: status.HTTP_400_BAD_REQUEST,
    ErrorCode.SUMMARY_ALREADY_PENDING: status.HTTP_409_CONFLICT,
    ErrorCode.SUMMARY_PROVIDER_ERROR: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.SUMMARY_RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.QUEUE_FULL: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.IMPORT_TOO_LARGE: status.HTTP_413_CONTENT_TOO_LARGE,
    ErrorCode.IMPORT_JOB_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.DECOMPILER_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.DECOMPILER_TIMEOUT: status.HTTP_504_GATEWAY_TIMEOUT,
    ErrorCode.DECOMPILER_FAILED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.DECOMPILER_OUTPUT_TOO_LARGE: status.HTTP_413_CONTENT_TOO_LARGE,
    ErrorCode.ANALYSIS_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.LAST_VIEW_DELETE_FORBIDDEN: status.HTTP_400_BAD_REQUEST,
    ErrorCode.PUBLIC_MODE_FORBIDDEN: status.HTTP_403_FORBIDDEN,
    ErrorCode.GHIDRA_PROGRAM_MISMATCH: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


class AppError(Exception):
    """Raise anywhere in services/routers; the handler below renders it as E4."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.http_status = http_status or _DEFAULT_STATUS[code]


def _envelope(
    code: ErrorCode, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return ErrorEnvelope(error=ErrorBody(code=code, message=message, details=details)).model_dump(
        mode="json"
    )


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content=_envelope(exc.code, exc.message, exc.details),
    )


async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=_envelope(
            ErrorCode.VALIDATION_ERROR,
            "Request validation failed.",
            {"errors": exc.errors()},
        ),
    )


async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Wrap FastAPI/Starlette's own HTTPException (e.g. 404 for unknown routes,
    405 for wrong method) in the same E4 envelope as our own AppError."""
    code = ErrorCode.VALIDATION_ERROR if exc.status_code == 422 else ErrorCode.INTERNAL_ERROR
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        message = "Not found."
    else:
        message = str(exc.detail) if exc.detail else "Request failed."
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(code, message),
    )


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    # Never leak internals to the client; the traceback goes to structured logs
    # via the logging middleware / exception-logging hook, not the response body.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_envelope(ErrorCode.INTERNAL_ERROR, "An unexpected error occurred."),
    )


__all__ = [
    "AppError",
    "ErrorBody",
    "ErrorCode",
    "ErrorEnvelope",
    "app_error_handler",
    "http_exception_handler",
    "unhandled_exception_handler",
    "validation_error_handler",
]
