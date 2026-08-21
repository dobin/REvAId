"""View use cases — read-only listing (pulled forward from I6 for I5).

Only enough to let the frontend resolve a `viewId` for the required
`GET /functions/{id}/neighbours` query param. Camera/node persistence, view
CRUD, and duplication remain I6 scope.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.errors import AppError, ErrorCode
from graphrev.repositories.binaries import get_binary_by_id
from graphrev.repositories.views import list_views_by_binary
from graphrev.schemas.view import ViewSummaryDto, view_summary_from_view


async def list_views_dto(session: AsyncSession, binary_id: int) -> list[ViewSummaryDto]:
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )
    views = await list_views_by_binary(session, binary_id=binary_id)
    return [view_summary_from_view(view) for view in views]
