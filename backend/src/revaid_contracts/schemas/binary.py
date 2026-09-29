"""``GET /binaries`` DTO (E1) — TAD §3.4 ``BinarySummaryDto``."""

from __future__ import annotations

from revaid_contracts.common import ApiModel

__all__ = ["BinarySummaryDto"]


class BinarySummaryDto(ApiModel):
    id: int
    name: str
    version: str
    analysis_image_base: int | None
    function_count: int
    edge_count: int
    #: Viewer-owned preference; always ``None`` on the analysis-only listing.
    last_view_id: int | None = None
    created_at: str
