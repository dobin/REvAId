"""Viewer logging setup delegating to the shared structured logger."""

from __future__ import annotations

from revaid_contracts.logging import (
    bind_request_id,
    clear_request_context,
    configure_logging,
    get_logger,
    log_event,
    restore_uvicorn_formatters,
)

__all__ = [
    "bind_request_id",
    "clear_request_context",
    "configure_logging",
    "get_logger",
    "log_event",
    "restore_uvicorn_formatters",
]
