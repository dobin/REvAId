"""View seeding helpers (B9 and operator-curated featured functions).

Written now, called by the ingestion pipeline in I2: every binary must have at
least one view so the picker is never empty after ingestion.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.core.config import get_settings
from graphrev.core.ids import random_view_id
from graphrev.db.models import Function, View, ViewNode


async def seed_featured_view_nodes(session: AsyncSession, view: View) -> None:
    """Copy this binary's featured functions into a newly created view.

    Featured membership is a creation-time template, not a live link: once
    these rows exist, normal view edits are authoritative. Independent root
    provenance avoids inventing call relationships between curated entries.
    """
    featured_ids = list(
        (
            await session.execute(
                select(Function.id)
                .where(Function.binary_id == view.binary_id, Function.is_featured.is_(True))
                .order_by(Function.address, Function.id)
            )
        ).scalars()
    )
    if not featured_ids:
        return

    now = utc_now_iso()
    view.root_function_id = featured_ids[0]
    view.updated_at = now
    session.add_all(
        [
            ViewNode(
                view_id=view.id,
                function_id=function_id,
                visible=True,
                collapsed=False,
                color=None,
                pos_x=0.0,
                pos_y=0.0,
                pinned=False,
                origin_function_id=None,
                origin_kind="root",
                origin_implied=False,
                created_at=now,
                updated_at=now,
            )
            for function_id in featured_ids
        ]
    )
    await session.flush()


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
                await seed_featured_view_nodes(session, view)
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
    await seed_featured_view_nodes(session, view)
    return view
