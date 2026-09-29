"""``POST /functions/{id}/summary`` request DTO (responses live in ``revaid_contracts``)."""

from __future__ import annotations

from pydantic import Field

from revaid.summarization.queue import MAX_PRIORITY, MIN_PRIORITY
from revaid_contracts.common import ApiModel


class SummaryDemandRequestDto(ApiModel):
    """``POST /functions/{id}/summary`` request body.

    ``reason`` is logging-only (card|table_row|detail|prefetch); it never
    affects queueing behaviour, only what shows up in structured logs.

    ``priority`` is bounded to `SummaryQueue`'s own
    [`MIN_PRIORITY`, `MAX_PRIORITY`] range at the DTO layer, so an
    out-of-range value fails FastAPI's 422 validation *before* any DB write
    happens — previously an out-of-range priority reached
    `services.summary_service.demand_summary`, whose own `queue.enqueue`
    raised `ValueError` (an unhandled 500) after the row had already been
    flipped to `summary_status='pending'`, stranding it there until the
    next boot's `recover_pending_summaries` sweep.
    """

    priority: int = Field(ge=MIN_PRIORITY, le=MAX_PRIORITY)
    reason: str | None = None
