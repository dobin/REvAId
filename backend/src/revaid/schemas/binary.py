"""``BinaryWithCounts`` → ``BinarySummaryDto`` mapping (E1)."""

from __future__ import annotations

from revaid.repositories.binaries import BinaryWithCounts
from revaid_contracts.schemas.binary import BinarySummaryDto


def binary_summary_from_row(
    row: BinaryWithCounts, *, last_view_id: int | None = None
) -> BinarySummaryDto:
    """Compose an analysis binary with optional viewer preference data."""
    return BinarySummaryDto(
        id=row.binary.id,
        name=row.binary.name,
        version=row.binary.version,
        analysis_image_base=row.binary.analysis_image_base,
        function_count=row.function_count,
        edge_count=row.edge_count,
        last_view_id=last_view_id,
        created_at=row.binary.created_at,
    )
