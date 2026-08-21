"""Lifespan startup hooks (C5b restart recovery, F1b threshold recompute).

Both hooks are called once from ``main.py``'s lifespan, before the app starts
serving traffic.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.config import Settings
from graphrev.core.logging import get_logger

logger = get_logger(__name__)

_UTILITY_THRESHOLD_KEY = "utility_fanin_threshold"


async def recover_pending_summaries(session: AsyncSession) -> int:
    """C5b: no function may display "Analyzing..." with no worker behind it.

    Any row left ``pending`` from a previous process (crash, restart) is reset
    to ``none``; the client will re-request on next render.
    """
    result = cast(
        "CursorResult[Any]",
        await session.execute(
            text("UPDATE functions SET summary_status = 'none' WHERE summary_status = 'pending'")
        ),
    )
    await session.commit()
    count = result.rowcount or 0
    if count:
        logger.info("startup.recovered_pending_summaries", count=count)
    return count


async def recompute_utility_if_threshold_changed(session: AsyncSession, settings: Settings) -> bool:
    """F1b: a threshold change must never require re-ingestion.

    Compares ``Settings.utility_fanin_threshold`` against the last-applied
    value recorded in ``app_meta``. Only runs the UPDATE, and only rewrites
    ``app_meta``, when the value actually changed.
    """
    row = await session.execute(
        text("SELECT value FROM app_meta WHERE key = :key"), {"key": _UTILITY_THRESHOLD_KEY}
    )
    stored = row.scalar_one_or_none()
    current = str(settings.utility_fanin_threshold)

    if stored == current:
        return False

    await session.execute(
        text("UPDATE functions SET is_utility = (fan_in > :threshold)"),
        {"threshold": settings.utility_fanin_threshold},
    )
    await session.execute(
        text(
            "INSERT INTO app_meta (key, value) VALUES (:key, :value) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
        ),
        {"key": _UTILITY_THRESHOLD_KEY, "value": current},
    )
    await session.commit()
    logger.info(
        "startup.recomputed_utility",
        previous_threshold=stored,
        new_threshold=current,
    )
    return True
