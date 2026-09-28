"""Viewer-specific application errors and HTTP exception handlers."""

from __future__ import annotations

from revaid_contracts.errors import ErrorBody, ErrorCode, ErrorEnvelope
from revaid_contracts.http_errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_error_handler,
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
