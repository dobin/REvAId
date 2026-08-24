"""SSE event payload DTOs (TAD §4.2 #22, E5/E5a/E5b).

These are rendered as the ``data:`` line of an SSE frame
(:func:`graphrev.events.sse.format_sse`), so — unlike every other DTO in
``schemas/`` — they are turned into plain ``dict``s via ``model_dump(mode=
"json", by_alias=True)`` rather than returned from a FastAPI route directly.
They still inherit :class:`~graphrev.schemas.common.ApiModel` so the wire
shape is the same camelCase contract as every REST response (TAD §4).
"""

from __future__ import annotations

from graphrev.schemas.common import ApiModel


class SummaryEventDto(ApiModel):
    """``event: summary`` (E5a — carries the full result so every surface
    patches in place with no refetch, TAD §4.3 #12's sibling event)."""

    function_id: int
    summary_status: str
    summary_short: str | None = None
    summary_model: str | None = None
    low_confidence: bool = False
    generated_at: str | None = None
    error_code: str | None = None


class QueueEventDto(ApiModel):
    """``event: queue`` (E5b) — mirrors `QueueSnapshotDto`'s counters only;
    the chip re-fetches `GET /queue` for the full listing on demand."""

    in_flight_count: int
    queued_count: int
    paused_until: str | None = None


class BinaryEventDto(ApiModel):
    """``event: binary`` — ingestion completed / binary deleted."""

    binary_id: int
    kind: str  # "imported" | "deleted"
