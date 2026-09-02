"""Default-view seeding helper (B9).

Written now, called by the ingestion pipeline in I2: every binary must have at
least one view so the picker is never empty after ingestion.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.core.config import get_settings
from graphrev.core.ids import random_view_id
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
    # ADR 0006: in public mode the seeded default view is still a shared
    # reference point for the *owner*, so its id must not be enumerable
    # either. Randomize it up front so enabling public mode on a fresh DB
    # never leaves guessable low-id views behind.
    if get_settings().public_mode:
        for _attempt in range(3):
            try:
                view.id = random_view_id()
                session.add(view)
                await session.flush()
                return view
            except IntegrityError:
                await session.rollback()
                # Rebuild a fresh View — the failed flush invalidated the
                # previous instance's insert state.
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
        # Vanishingly rare (2^53 space); fall back to autoincrement rather
        # than failing ingestion outright.
    session.add(view)
    await session.flush()
    return view
