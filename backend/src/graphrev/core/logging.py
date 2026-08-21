"""Structured logging (F2).

structlog renders JSON in prod (``Settings.log_json``) and a human-readable
console format in dev. A ``request_id`` contextvar is bound by ASGI middleware
so every log line within one HTTP request can be correlated.

F2 asks specifically for "structured logging of ingestion and LLM calls" — the
PRD does not require structured *request* logging of the API itself, but the
mandatory-field helper below is generic so ingestion (I2) and the LLM worker
(I7) can both use it without re-deriving the field list.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

from graphrev.core.config import Settings

#: F2 — every ingestion and LLM-call log line must carry these fields so the
#: §1.4 engineering metrics (cache-hit rate, failure rate, throughput) can be
#: computed from logs alone, since there is no telemetry (AS13).
MANDATORY_EVENT_FIELDS = (
    "event",
    "function_id",
    "binary_id",
    "duration_ms",
    "adapter",
    "model",
    "outcome",
)


def configure_logging(settings: Settings) -> None:
    """Configure structlog + stdlib logging. Call once at process startup."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]


def bind_request_id(request_id: str) -> None:
    bind_contextvars(request_id=request_id)


def clear_request_context() -> None:
    clear_contextvars()


def log_event(
    logger: structlog.stdlib.BoundLogger,
    event: str,
    *,
    function_id: int | None = None,
    binary_id: int | None = None,
    duration_ms: float | None = None,
    adapter: str | None = None,
    model: str | None = None,
    outcome: str | None = None,
    **extra: Any,
) -> None:
    """Emit a log line carrying every :data:`MANDATORY_EVENT_FIELDS` entry (F2).

    Ingestion and LLM call sites should use this helper rather than
    ``logger.info(...)`` directly, so the mandatory-field contract can't drift.
    """
    logger.info(
        event,
        function_id=function_id,
        binary_id=binary_id,
        duration_ms=duration_ms,
        adapter=adapter,
        model=model,
        outcome=outcome,
        **extra,
    )
