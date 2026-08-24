"""``GET /queue`` / ``POST /queue/cancel-pending`` (TAD §4.2 endpoints 20-21, E1c)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Function
from graphrev.events.bus import EventBus
from graphrev.schemas.summary import (
    CancelPendingResponseDto,
    InFlightItemDto,
    QueuedItemDto,
    QueueSnapshotDto,
)
from graphrev.summarization.queue import SummaryQueue


async def get_queue_snapshot(session: AsyncSession, queue: SummaryQueue) -> QueueSnapshotDto:
    snapshot = queue.snapshot()

    ids = {item.function_id for item in snapshot.queued} | set(snapshot.inflight_function_ids)
    display_names: dict[int, str] = {}
    if ids:
        rows = await session.execute(
            select(Function.id, Function.name_analyst, Function.name_ghidra).where(
                Function.id.in_(ids)
            )
        )
        display_names = {
            fn_id: name_analyst or name_ghidra for fn_id, name_analyst, name_ghidra in rows
        }

    queued = [
        QueuedItemDto(
            function_id=item.function_id,
            display_name=display_names.get(item.function_id, "?"),
            priority=item.priority,
        )
        for item in snapshot.queued
    ]
    in_flight = [
        InFlightItemDto(
            function_id=function_id,
            display_name=display_names.get(function_id, "?"),
        )
        for function_id in snapshot.inflight_function_ids
    ]

    return QueueSnapshotDto(
        in_flight=in_flight,
        queued=queued,
        in_flight_count=len(in_flight),
        queued_count=len(queued),
        paused_until=_iso_or_none(snapshot.paused_until),
    )


async def cancel_all_pending(
    queue: SummaryQueue, event_bus: EventBus | None = None
) -> CancelPendingResponseDto:
    """Drop every queued-but-not-started item (endpoint 21). In-flight work
    is never touched (C8)."""
    snapshot = queue.snapshot()
    cancelled = 0
    for item in snapshot.queued:
        for _ in range(item.demand):
            queue.release(item.function_id)
        cancelled += 1
    if event_bus is not None:
        after = queue.snapshot()
        event_bus.publish(
            "queue",
            {
                "inFlightCount": len(after.inflight_function_ids),
                "queuedCount": len(after.queued),
                "pausedUntil": None,
            },
        )
    return CancelPendingResponseDto(cancelled_count=cancelled)


def _iso_or_none(paused_until_monotonic: float | None) -> str | None:
    """`SummaryQueue.paused_until()` is a monotonic-clock deadline, not a wall
    timestamp; render it as "now" in ISO form only as a presence flag — the
    exact wall-clock value is not meaningful across the monotonic clock,
    which is why the DTO field only needs to say "queue is currently
    paused", matching the TAD payload's `pausedUntil: null` when not
    paused."""
    if paused_until_monotonic is None:
        return None
    return utc_now_iso()
