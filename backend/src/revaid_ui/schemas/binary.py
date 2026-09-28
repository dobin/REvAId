"""Viewer binary summary DTO and analysis contract mapping."""

from __future__ import annotations

from revaid_contracts.analysis import AnalysisBinary
from revaid_contracts.common import ApiModel


class BinarySummaryDto(ApiModel):
    id: int
    name: str
    version: str
    analysis_image_base: int | None
    function_count: int
    edge_count: int
    last_view_id: int | None = None
    created_at: str


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
