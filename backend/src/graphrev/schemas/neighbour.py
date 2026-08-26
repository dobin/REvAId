"""``GET /functions/{id}/neighbours`` DTOs (E2, E2a, E2b) — TAD §3.4/§4.3."""

from __future__ import annotations

from graphrev.schemas.common import ApiModel


class NeighbourRowDto(ApiModel):
    """One row in a card's caller/callee table.

    Deliberately narrow — no code, no long summary (TAD §3.4).
    """

    id: int
    address: int
    display_name: str
    #: C13 auto-display: the LLM-proposed name, when one exists (display_name
    #: already reflects the `name_analyst ?? name_llm ?? name_ghidra`
    #: precedence — exposed so the UI can badge/tooltip the raw Ghidra name).
    name_llm: str | None
    is_renamed: bool
    summary_short: str | None
    summary_status: str
    summary_low_confidence: bool
    kind: str
    on_canvas: bool
    is_utility: bool
    utility_source: str
    fan_in: int
    is_self: bool
    has_notes: bool


class NeighbourPageDto(ApiModel):
    function_id: int
    direction: str
    group: str
    rows: list[NeighbourRowDto]
    total: int
    total_primary: int
    total_utility: int
    limit: int
    offset: int
    callers_suppressed: bool
    may_be_incomplete: bool
