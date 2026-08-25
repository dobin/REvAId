"""`SummaryQueue` — the server-side priority queue for LLM summarisation
(TAD §2.6, C2c/C5/C8, docs/specs/PLAN-I7-I8-I9-I13.md §3.3).

Design constraints, all load-bearing (do not "simplify" any of these away):

- **Dedup:** one :class:`QueueItem` per ``function_id``, *ever*. A repeat
  request upgrades the existing item's priority in place (mark-stale-and
  -reinsert into the heap; the stale heap copy is discarded on pop) rather
  than creating a second item.
- **Cancel is advisory and refcounted:** :meth:`SummaryQueue.release` (the
  server side of ``DELETE /functions/{id}/summary``) decrements a per-item
  demand refcount; the item is dropped only at ``demand == 0`` **and** only
  if it is not already ``_inflight``. In-flight work always completes and is
  cached (C8) — cancellation never orphans a worker.
- **Bounded:** at ``queue_max_depth`` (default 500, F1). Overflow evicts the
  lowest-priority, oldest *not-yet-started* item and logs a warning, rather
  than growing unbounded or rejecting new demand outright.
- **Queue-wide pause:** a provider rate limit pauses the *whole* queue
  (``_paused_until``), not just the offending item (§5.1) — the point is one
  banner in the UI, not twelve card-level errors.

This module is pure in-process state (an ``asyncio.PriorityQueue`` plus a
couple of dicts) — no DB access, no adapter calls. ``summarization/worker.py``
(next commit boundary) is what pops items, calls the adapter, and persists
results.
"""

from __future__ import annotations

import asyncio
import itertools
import time
from dataclasses import dataclass, field

from graphrev.core.clock import utc_now_iso

#: TAD §2.6 priority ladder — lower wins. 0 is the selected card's own
#: summary; 3 is off-screen/lookahead. Keep in sync with
#: `frontend/src/api/types.ts`'s `Priority` union (hand-mirrored, AM per repo
#: convention — see docs/specs/PLAN-I7-I8-I9-I13.md §0).
MIN_PRIORITY = 0
MAX_PRIORITY = 3


@dataclass(order=True)
class QueueItem:
    """One function's place in the queue.

    Ordering is by ``(priority, seq)`` only — ``function_id``/``demand`` are
    excluded from comparison (`compare=False`) so two items for different
    functions at the same priority still order deterministically by arrival,
    and so mutating ``demand``/``function_id`` in place never corrupts heap
    order.
    """

    priority: int
    seq: int
    function_id: int = field(compare=False)
    demand: int = field(compare=False, default=0)
    #: Set on the stale copy left behind by a priority upgrade so the pop
    #: loop can silently discard it instead of re-processing a function
    #: that already has a fresher, live `QueueItem` in `_index`.
    superseded: bool = field(compare=False, default=False)


@dataclass(frozen=True, slots=True)
class QueueSnapshot:
    """`GET /queue` payload shape (TAD endpoint 20) — not the DTO itself,
    just the data the router needs to build one."""

    queued: tuple[QueueItem, ...]
    inflight_function_ids: tuple[int, ...]
    paused_until: float | None
    #: function_id -> ISO-8601 UTC timestamp the item was popped and marked
    #: in-flight. Lets `InFlightItemDto.started_at` show elapsed time in the
    #: queue chip instead of always being `None`.
    inflight_started_at: dict[int, str] = field(default_factory=dict)


class QueueFullError(Exception):
    """Raised by :meth:`SummaryQueue.enqueue` only in the (rare) case that
    even eviction cannot make room — e.g. every item in the queue is already
    `_inflight`. Routers should map this to ``ErrorCode.QUEUE_FULL``."""


class SummaryQueue:
    """Async priority queue of pending summary requests, keyed by function.

    Not thread-safe across event loops (none of this codebase is); safe for
    concurrent ``asyncio`` tasks within one process/loop, which is the only
    concurrency this app has (TAD §1.3).
    """

    def __init__(self, *, max_depth: int) -> None:
        self._max_depth = max_depth
        self._pq: asyncio.PriorityQueue[QueueItem] = asyncio.PriorityQueue()
        #: function_id -> the live (non-superseded) QueueItem, whether it is
        #: still sitting in `_pq` or currently `_inflight`. Removed only once
        #: the function leaves the queue entirely (drained+cancelled, or
        #: completed by the worker).
        self._index: dict[int, QueueItem] = {}
        self._inflight: set[int] = set()
        #: function_id -> ISO-8601 UTC timestamp set when `pop()` marks it
        #: in-flight, cleared by `complete()`/`requeue_inflight()`. Feeds
        #: `InFlightItemDto.started_at` (queue chip elapsed-time display).
        self._inflight_started_at: dict[int, str] = {}
        self._seq_counter = itertools.count()
        self._paused_until: float | None = None

    # -- introspection ------------------------------------------------------

    def __len__(self) -> int:
        """Number of distinct functions currently queued (not yet popped)."""
        return sum(1 for item in self._index.values() if item.function_id not in self._inflight)

    def depth(self) -> int:
        return len(self)

    def is_queued(self, function_id: int) -> bool:
        return function_id in self._index and function_id not in self._inflight

    def is_inflight(self, function_id: int) -> bool:
        return function_id in self._inflight

    def paused_until(self) -> float | None:
        """Monotonic-clock deadline the queue is paused until, or ``None``."""
        if self._paused_until is not None and self._paused_until <= time.monotonic():
            self._paused_until = None
        return self._paused_until

    def paused_until_iso(self) -> str | None:
        """`paused_until()` rendered for the wire (`GET /queue`, `queue` SSE
        events). `SummaryQueue.paused_until()` is a monotonic-clock deadline,
        not a wall timestamp, so this only signals *presence* ("queue is
        currently paused") via "now" in ISO form — the exact wall-clock value
        is not meaningful across the monotonic clock. Both
        `queue_service.get_queue_snapshot` and `summary_service`'s queue-event
        publisher must use this one implementation rather than each
        hand-rolling their own conversion."""
        if self.paused_until() is None:
            return None
        return utc_now_iso()

    def snapshot(self) -> QueueSnapshot:
        queued = tuple(
            sorted(
                (item for item in self._index.values() if item.function_id not in self._inflight),
                key=lambda it: (it.priority, it.seq),
            )
        )
        return QueueSnapshot(
            queued=queued,
            inflight_function_ids=tuple(self._inflight),
            paused_until=self.paused_until(),
            inflight_started_at=dict(self._inflight_started_at),
        )

    # -- mutation ------------------------------------------------------------

    def enqueue(self, function_id: int, priority: int) -> QueueItem:
        """Add demand for ``function_id`` at ``priority``.

        - If already queued or in-flight: increments ``demand`` and, if the
          new priority is numerically lower (more urgent), upgrades it via
          mark-stale-and-reinsert.
        - If new: creates a fresh item, incrementing depth. Enforces
          ``max_depth`` by evicting the lowest-priority, oldest *queued*
          (not in-flight) item if necessary.
        """
        if not (MIN_PRIORITY <= priority <= MAX_PRIORITY):
            raise ValueError(
                f"priority must be in [{MIN_PRIORITY}, {MAX_PRIORITY}], got {priority}"
            )

        existing = self._index.get(function_id)
        if existing is not None:
            existing.demand += 1
            if priority < existing.priority and function_id not in self._inflight:
                self._upgrade(existing, priority)
            return self._index[function_id]

        if len(self._index) >= self._max_depth:
            self._evict_one()

        item = QueueItem(priority=priority, seq=next(self._seq_counter), function_id=function_id)
        item.demand = 1
        self._index[function_id] = item
        self._pq.put_nowait(item)
        return item

    def release(self, function_id: int) -> None:
        """Server side of ``DELETE /functions/{id}/summary`` — decrement
        demand; drop the item only at ``demand == 0`` and only if it is not
        `_inflight` (C8). In-flight items are marked so a *future* pop of a
        superseded duplicate is impossible, but the in-flight call itself is
        never interrupted."""
        item = self._index.get(function_id)
        if item is None:
            return
        item.demand = max(0, item.demand - 1)
        if item.demand == 0 and function_id not in self._inflight:
            item.superseded = True
            del self._index[function_id]

    async def pop(self) -> QueueItem:
        """Block until an item is available, then mark it in-flight and
        return it. Silently discards superseded (stale, upgraded-away)
        copies and items that were fully released while still queued."""
        while True:
            item = await self._pq.get()
            if item.superseded:
                continue
            current = self._index.get(item.function_id)
            if current is not item:
                # This exact object was superseded by an upgrade; the fresh
                # copy is still in the heap (or already popped elsewhere).
                continue
            if item.demand <= 0:
                # Fully released while queued.
                self._index.pop(item.function_id, None)
                continue
            self._inflight.add(item.function_id)
            self._inflight_started_at[item.function_id] = utc_now_iso()
            return item

    def complete(self, function_id: int) -> None:
        """Worker calls this after persisting a result (success or failure)."""
        self._inflight.discard(function_id)
        self._inflight_started_at.pop(function_id, None)
        self._index.pop(function_id, None)

    def requeue_inflight(self, function_id: int, priority: int | None = None) -> None:
        """Move an in-flight item back onto the queue, preserving its demand
        refcount (used when a :class:`RateLimitError` means the *work itself*
        was never actually done — the item must be retried, not treated as
        completed or failed). ``priority`` defaults to the item's own
        priority; no-op if the function is not currently in-flight."""
        if function_id not in self._inflight:
            return
        current = self._index.get(function_id)
        demand = current.demand if current is not None else 1
        effective_priority = (
            priority
            if priority is not None
            else (current.priority if current is not None else MAX_PRIORITY)
        )
        if current is not None:
            current.superseded = True
        self._inflight.discard(function_id)
        self._inflight_started_at.pop(function_id, None)
        replacement = QueueItem(
            priority=effective_priority,
            seq=next(self._seq_counter),
            function_id=function_id,
            demand=demand,
        )
        self._index[function_id] = replacement
        self._pq.put_nowait(replacement)

    def pause(self, retry_after_seconds: float) -> None:
        """Queue-wide rate-limit backoff (§5.1) — one banner, not N errors."""
        self._paused_until = time.monotonic() + max(0.0, retry_after_seconds)

    # -- internals ------------------------------------------------------------

    def _upgrade(self, item: QueueItem, new_priority: int) -> None:
        item.superseded = True
        replacement = QueueItem(
            priority=new_priority,
            seq=next(self._seq_counter),
            function_id=item.function_id,
            demand=item.demand,
        )
        self._index[item.function_id] = replacement
        self._pq.put_nowait(replacement)

    def _evict_one(self) -> None:
        """Drop the lowest-priority, oldest queued (never in-flight) item to
        make room under `max_depth`. Logging is the caller's/worker's job —
        this module has no logger dependency by design (kept pure/testable)."""
        candidates = [
            item for item in self._index.values() if item.function_id not in self._inflight
        ]
        if not candidates:
            raise QueueFullError("queue is at capacity and every item is in-flight")
        victim = max(candidates, key=lambda it: (it.priority, it.seq))
        victim.superseded = True
        del self._index[victim.function_id]
