"""Default-view seeding helper (B9).

Written now, called by the ingestion pipeline in I2: every binary must have at
least one view so the picker is never empty after ingestion.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import View


async def create_default_view(session: AsyncSession, binary_id: int, name: str = "Default") -> View:
    now = utc_now_iso()
    view = View(
        binary_id=binary_id,
        name=name,
        root_function_id=None,
        camera_x=0.0,
        camera_y=0.0,
        camera_zoom=1.0,
        created_at=now,
        updated_at=now,
    )
    session.add(view)
    await session.flush()
    return view
