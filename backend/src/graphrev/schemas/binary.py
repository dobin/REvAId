"""``GET /binaries`` DTOs (E1) — TAD §3.4 ``BinarySummaryDto``."""

from __future__ import annotations

from graphrev.repositories.binaries import BinaryWithCounts
from graphrev.schemas.common import ApiModel


class BinarySummaryDto(ApiModel):
    id: int
    name: str
    version: str
    analysis_image_base: int | None
    function_count: int
    edge_count: int
    last_view_id: int | None
    created_at: str


def binary_summary_from_row(
    row: BinaryWithCounts, *, redact_last_view: bool = False
) -> BinarySummaryDto:
    """The single mapping function from a repository row to the wire DTO.

    `redact_last_view` (ADR 0006) nulls `last_view_id` in public mode, where
    it would otherwise leak the owner's last-used view id to anonymous
    browsers.
    """
    return BinarySummaryDto(
        id=row.binary.id,
        name=row.binary.name,
        version=row.binary.version,
        analysis_image_base=row.binary.analysis_image_base,
        function_count=row.function_count,
        edge_count=row.edge_count,
        last_view_id=None if redact_last_view else row.binary.last_view_id,
        created_at=row.binary.created_at,
    )
