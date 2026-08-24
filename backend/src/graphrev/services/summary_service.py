"""Summary demand/cancel/regenerate façade (TAD §4.2 endpoints 17-19, C2/C3/C7/C8).

Cache-first (C3): a request for a function already ``summary_status='ready'``
never touches the queue. Demand/cancel are advisory refcounts forwarded
directly to :class:`~graphrev.summarization.queue.SummaryQueue`; this module's
only DB responsibility is flipping ``summary_status`` to ``'pending'`` when
new work is actually queued, so the client's next read reflects reality
immediately (it does not wait for a worker to pick the item up).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.errors import AppError, ErrorCode
from graphrev.events.bus import EventBus
from graphrev.repositories.functions import get_function_by_id
from graphrev.schemas.summary import SummaryDemandResponseDto
from graphrev.summarization.queue import MIN_PRIORITY, SummaryQueue

#: Statuses from which a demand request actually schedules work. `ready` is
#: served straight from cache (C3); `pending` is already queued (dedup, no
#: new item). `none`/`error`/`stale` all need a fresh generation.
_NEEDS_GENERATION_STATUSES = frozenset({"none", "error", "stale"})


async def demand_summary(
    session: AsyncSession,
    queue: SummaryQueue,
    *,
    function_id: int,
    priority: int,
    event_bus: EventBus | None = None,
) -> SummaryDemandResponseDto:
    """``POST /functions/{id}/summary`` (C2, C3, C5a — never blocks)."""
    fn = await get_function_by_id(session, function_id)
    if fn is None:
        raise AppError(
            ErrorCode.FUNCTION_NOT_FOUND,
            f"No function {function_id}.",
            details={"functionId": function_id},
        )

    if fn.summary_status == "ready":
        return SummaryDemandResponseDto(
            function_id=function_id,
            summary_status="ready",
            summary_short=fn.summary_short,
        )

    if fn.summary_status in _NEEDS_GENERATION_STATUSES:
        await session.execute(
            text("UPDATE functions SET summary_status = 'pending' WHERE id = :id"),
            {"id": function_id},
        )
        await session.commit()

    queue.enqueue(function_id, priority)
    position = _queue_position(queue, function_id)
    _publish_queue_event(event_bus, queue)
    return SummaryDemandResponseDto(
        function_id=function_id,
        summary_status="pending",
        queue_position=position,
    )


def release_summary_demand(
    queue: SummaryQueue, *, function_id: int, event_bus: EventBus | None = None
) -> None:
    """``DELETE /functions/{id}/summary`` (C8) — advisory, refcounted."""
    queue.release(function_id)
    _publish_queue_event(event_bus, queue)


async def regenerate_summary(
    session: AsyncSession,
    queue: SummaryQueue,
    *,
    function_id: int,
    event_bus: EventBus | None = None,
) -> SummaryDemandResponseDto:
    """``POST /functions/{id}/summary/regenerate`` (C7) — force regeneration,
    ignore the cache, priority forced to 0. ``notes`` is untouched by this
    call (it is a separate analyst-owned field the worker reads, never
    writes)."""
    fn = await get_function_by_id(session, function_id)
    if fn is None:
        raise AppError(
            ErrorCode.FUNCTION_NOT_FOUND,
            f"No function {function_id}.",
            details={"functionId": function_id},
        )

    await session.execute(
        text("UPDATE functions SET summary_status = 'pending' WHERE id = :id"),
        {"id": function_id},
    )
    await session.commit()

    queue.enqueue(function_id, MIN_PRIORITY)
    position = _queue_position(queue, function_id)
    _publish_queue_event(event_bus, queue)
    return SummaryDemandResponseDto(
        function_id=function_id,
        summary_status="pending",
        queue_position=position,
    )


def _publish_queue_event(event_bus: EventBus | None, queue: SummaryQueue) -> None:
    """E5b — the chip's live counters. Best-effort: a missing bus (e.g. a
    unit test constructing this service directly) is a no-op, not an error."""
    if event_bus is None:
        return
    snapshot = queue.snapshot()
    event_bus.publish(
        "queue",
        {
            "inFlightCount": len(snapshot.inflight_function_ids),
            "queuedCount": len(snapshot.queued),
            "pausedUntil": None,
        },
    )


def _queue_position(queue: SummaryQueue, function_id: int) -> int | None:
    """1-based position among queued-not-inflight items, or `None` if the
    item is already in-flight (there is no meaningful "position" for it)."""
    if queue.is_inflight(function_id):
        return None
    snapshot = queue.snapshot()
    for index, item in enumerate(snapshot.queued, start=1):
        if item.function_id == function_id:
            return index
    return None
