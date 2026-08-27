"""Lifespan startup hooks (C5b restart recovery, F1b threshold recompute).

Both hooks are called once from ``main.py``'s lifespan, before the app starts
serving traffic.
"""

from __future__ import annotations

from typing import cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.config import Settings
from graphrev.core.logging import get_logger
from graphrev.summarization.queue import MAX_PRIORITY, SummaryQueue

logger = get_logger(__name__)

_UTILITY_THRESHOLD_KEY = "utility_fanin_threshold"


async def recover_pending_summaries(session: AsyncSession, queue: SummaryQueue) -> int:
    """C5b: no function may display "Analyzing..." with no worker behind it.

    The queue is process-local, so any durable ``pending`` rows left by a
    previous process must be restored into the new queue before workers
    start. Their original priority and demand count are not durable; restart
    recovery uses the lowest priority and one demand. A later visible request
    can promote the item using normal queue semantics.

    If the configured queue capacity was lowered since the previous process,
    an evicted item cannot truthfully remain ``pending``. Reset only those
    un-restorable rows to ``none`` so they can be requested again.
    """
    result = await session.execute(text("SELECT id FROM functions WHERE summary_status = 'pending'"))
    function_ids = [cast(int, function_id) for function_id in result.scalars()]
    for function_id in function_ids:
        queue.enqueue(function_id, MAX_PRIORITY)

    # `enqueue` evicts a queued item if capacity was reduced. Preserve
    # `pending` only for the IDs that are actually backed by this new queue.
    unqueued_ids = [function_id for function_id in function_ids if not queue.is_queued(function_id)]
    for function_id in unqueued_ids:
        await session.execute(
            text("UPDATE functions SET summary_status = 'none' WHERE id = :function_id"),
            {"function_id": function_id},
        )
    await session.commit()
    restored_count = len(function_ids) - len(unqueued_ids)
    if restored_count:
        logger.info("startup.recovered_pending_summaries", count=restored_count)
    if unqueued_ids:
        logger.warning("startup.pending_summaries_not_requeued", count=len(unqueued_ids))
    return restored_count


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
