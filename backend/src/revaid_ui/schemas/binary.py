"""``AnalysisBinary`` → ``BinarySummaryDto`` mapping for the viewer."""

from __future__ import annotations

from revaid_contracts.analysis import AnalysisBinary
from revaid_contracts.schemas.binary import BinarySummaryDto


def binary_summary_from_analysis(
    binary: AnalysisBinary, *, last_view_id: int | None
) -> BinarySummaryDto:
    return BinarySummaryDto(
        id=binary.id,
        name=binary.name,
        version=binary.version,
        analysis_image_base=binary.analysis_image_base,
        function_count=binary.function_count,
        edge_count=binary.edge_count,
        last_view_id=last_view_id,
        created_at=binary.created_at,
    )
