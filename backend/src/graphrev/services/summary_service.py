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
from graphrev.repositories.binaries import get_binary_by_id
from graphrev.repositories.functions import get_function_by_id
from graphrev.schemas.summary import SummaryDemandResponseDto
from graphrev.services.queue_service import queue_event_payload
from graphrev.summarization.queue import MIN_PRIORITY, QueueFullError, SummaryQueue

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

    # Enqueue BEFORE flipping the DB status: if `enqueue` fails (queue full —
    # `QueueFullError`, mapped to `QUEUE_FULL` below), the row must stay at
    # its previous status rather than being stranded at `pending` with
    # nothing actually queued to clear it (that stranding previously
    # required waiting for the next boot's `recover_pending_summaries`
    # sweep). `priority` itself is validated at the DTO layer
    # (`SummaryDemandRequestDto`, `ge=0, le=3`) before this function ever
    # runs, so `queue.enqueue`'s own `ValueError` here is unreachable via
    # the API — it only guards direct callers (tests, future call sites).
    try:
        queue.enqueue(function_id, priority)
    except QueueFullError as exc:
        raise AppError(
            ErrorCode.QUEUE_FULL,
            "The summarisation queue is full; try again shortly.",
            details={"functionId": function_id},
        ) from exc

    if fn.summary_status in _NEEDS_GENERATION_STATUSES:
        await session.execute(
            text("UPDATE functions SET summary_status = 'pending' WHERE id = :id"),
            {"id": function_id},
        )
        await session.commit()

    position = _queue_position(queue, function_id)
    _publish_pending_event(event_bus, function_id)
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

    # Same enqueue-before-DB-flip ordering as `demand_summary` above.
    try:
        queue.enqueue(function_id, MIN_PRIORITY)
    except QueueFullError as exc:
        raise AppError(
            ErrorCode.QUEUE_FULL,
            "The summarisation queue is full; try again shortly.",
            details={"functionId": function_id},
        ) from exc

    await session.execute(
        text("UPDATE functions SET summary_status = 'pending' WHERE id = :id"),
        {"id": function_id},
    )
    await session.commit()

    position = _queue_position(queue, function_id)
    _publish_pending_event(event_bus, function_id)
    _publish_queue_event(event_bus, queue)
    return SummaryDemandResponseDto(
        function_id=function_id,
        summary_status="pending",
        queue_position=position,
    )


async def clear_binary_summaries(
    session: AsyncSession,
    queue: SummaryQueue,
    *,
    binary_id: int,
    event_bus: EventBus | None = None,
) -> int:
    """``DELETE /binaries/{id}/summaries`` — TESTING affordance: null every
    LLM-owned summary column on every function of the binary and drop any
    queued (not in-flight) demand for them. Returns the affected row count.

    In-flight generations are NOT interrupted (C8 spirit): the worker will
    re-write a summary for that one function after this wipe; everything
    else stays clean until re-demanded."""
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )

    result = await session.execute(
        text(
            """
            UPDATE functions SET
                summary_short = NULL,
                summary_long = NULL,
                summary_status = 'none',
                summary_model = NULL,
                summary_error_code = NULL,
                summary_low_confidence = 0,
                summary_generated_at = NULL,
                summary_input_hash = NULL
            WHERE binary_id = :binary_id
            """
        ),
        {"binary_id": binary_id},
    )
    await session.commit()

    affected_ids = [
        row[0]
        for row in (
            await session.execute(
                text("SELECT id FROM functions WHERE binary_id = :binary_id"),
                {"binary_id": binary_id},
            )
        ).all()
    ]
    for function_id in affected_ids:
        queue.release(function_id)
        _publish_cleared_event(event_bus, function_id)
    _publish_queue_event(event_bus, queue)
    return len(affected_ids)


def _publish_cleared_event(event_bus: EventBus | None, function_id: int) -> None:
    """`summary` event for the ->none wipe, same shape as
    `_publish_pending_event` so `applySummaryEvent` needs no changes."""
    if event_bus is None:
        return
    event_bus.publish(
        "summary",
        {
            "functionId": function_id,
            "summaryStatus": "none",
            "summaryShort": None,
            "summaryModel": None,
            "lowConfidence": False,
            "generatedAt": None,
            "errorCode": None,
        },
    )


def _publish_pending_event(event_bus: EventBus | None, function_id: int) -> None:
    """E5a's `summary` event, published on the `->pending` transition too
    (previously only `ready`/`error` were pushed from the worker — see
    `main.py::_publish_summary_event`). Lets every open surface for this
    function show "generating" immediately rather than waiting for its own
    next poll/refetch. Shape matches `main.py`'s payload exactly, so
    `applySummaryEvent` on the frontend needs no changes."""
    if event_bus is None:
        return
    event_bus.publish(
        "summary",
        {
            "functionId": function_id,
            "summaryStatus": "pending",
            "summaryShort": None,
            "summaryModel": None,
            "lowConfidence": False,
            "generatedAt": None,
            "errorCode": None,
        },
    )


def _publish_queue_event(event_bus: EventBus | None, queue: SummaryQueue) -> None:
    """E5b — the chip's live counters. Best-effort: a missing bus (e.g. a
    unit test constructing this service directly) is a no-op, not an error."""
    if event_bus is None:
        return
    event_bus.publish("queue", queue_event_payload(queue))


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
