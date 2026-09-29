"""Viewer facade operations over analysis binaries and viewer preferences."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from revaid_contracts.analysis import AnalysisClient
from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_contracts.schemas.binary import BinarySummaryDto
from revaid_ui.repositories import views as views_repository
from revaid_ui.schemas.binary import binary_summary_from_analysis


async def list_binaries_from_analysis(
    analysis: AnalysisClient,
    viewer_session: AsyncSession,
    *,
    redact_last_view: bool = False,
) -> list[BinarySummaryDto]:
    binaries = await analysis.list_binaries()
    last_view_ids = (
        await views_repository.get_last_view_ids(
            viewer_session, binary_ids=[binary.id for binary in binaries]
        )
        if not redact_last_view
        else {}
    )
    return [
        binary_summary_from_analysis(binary, last_view_id=last_view_ids.get(binary.id))
        for binary in binaries
    ]


async def delete_binary_via_analysis(
    analysis: AnalysisClient,
    viewer_session: AsyncSession,
    *,
    binary_id: int,
    confirm: str,
) -> None:
    """Delete analysis facts remotely, then idempotently clean viewer state."""
    deleted = await analysis.delete_binary(binary_id, confirm)
    await views_repository.delete_views_by_binary(viewer_session, binary_id=binary_id)
    await viewer_session.commit()
    if not deleted:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}; stale viewer state was cleaned if present.",
            details={"binaryId": binary_id},
        )
