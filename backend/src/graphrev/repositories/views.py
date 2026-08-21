"""View repository — read-only listing (pulled forward from I6 for I5).

Every binary is guaranteed at least one `View` row by ingestion (B9,
`ingestion/pipeline.py`), so this module only needs a simple ordered list
query; no create/update/delete here yet (I6 scope).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.db.models import View


async def list_views_by_binary(session: AsyncSession, *, binary_id: int) -> list[View]:
    """All views for `binary_id`, ordered by id (creation order)."""
    result = await session.execute(
        select(View).where(View.binary_id == binary_id).order_by(View.id)
    )
    return list(result.scalars().all())
