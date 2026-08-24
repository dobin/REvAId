"""``GET /queue`` / ``POST /queue/cancel-pending`` (TAD §4.2 endpoints 20-21, E1c)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.db.models import Function
from graphrev.events.bus import EventBus
from graphrev.schemas.summary import (
    CancelPendingResponseDto,
    InFlightItemDto,
    QueuedItemDto,
    QueueSnapshotDto,
)
from graphrev.summarization.queue import SummaryQueue


def queue_event_payload(queue: SummaryQueue) -> dict[str, object]:
    """The `event: queue` SSE payload (E5b) — shared by every publish site
    (`summary_service.demand_summary`/`regenerate_summary`/
    `release_summary_demand`, and `cancel_all_pending` below) so
    `pausedUntil` is computed the same way everywhere instead of each call
    site hand-rolling (and, previously, hardcoding `None` for) its own
    dict."""
    snapshot = queue.snapshot()
    return {
        "inFlightCount": len(snapshot.inflight_function_ids),
        "queuedCount": len(snapshot.queued),
        "pausedUntil": queue.paused_until_iso(),
    }


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
            started_at=snapshot.inflight_started_at.get(function_id),
        )
        for function_id in snapshot.inflight_function_ids
    ]

    return QueueSnapshotDto(
        in_flight=in_flight,
        queued=queued,
        in_flight_count=len(in_flight),
        queued_count=len(queued),
        paused_until=queue.paused_until_iso(),
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
        event_bus.publish("queue", queue_event_payload(queue))
    return CancelPendingResponseDto(cancelled_count=cancelled)
