"""`SummaryQueue` unit tests (TAD §2.6/§7 I7 exit criteria):
dedup, priority upgrade, refcounted advisory cancel, bound/eviction, pause.
"""

from __future__ import annotations

import asyncio

import pytest

from graphrev.summarization.queue import QueueFullError, SummaryQueue


def test_enqueue_creates_one_item_per_function() -> None:
    q = SummaryQueue(max_depth=10)
    q.enqueue(1, priority=2)
    q.enqueue(2, priority=2)
    assert len(q) == 2


def test_duplicate_enqueue_does_not_create_second_item() -> None:
    q = SummaryQueue(max_depth=10)
    q.enqueue(1, priority=2)
    q.enqueue(1, priority=2)
    assert len(q) == 1


def test_duplicate_enqueue_increments_demand() -> None:
    q = SummaryQueue(max_depth=10)
    q.enqueue(1, priority=2)
    q.enqueue(1, priority=2)
    item = q._index[1]
    assert item.demand == 2


async def test_priority_upgrade_reorders_pop_order() -> None:
    q = SummaryQueue(max_depth=10)
    q.enqueue(1, priority=3)
    q.enqueue(2, priority=2)
    # Upgrade function 1 to priority 0 — it should now pop first.
    q.enqueue(1, priority=0)
    first = await q.pop()
    assert first.function_id == 1
    assert first.priority == 0


async def test_priority_upgrade_discards_stale_copy_on_pop() -> None:
    q = SummaryQueue(max_depth=10)
    q.enqueue(1, priority=3)
    q.enqueue(1, priority=0)
    first = await q.pop()
    assert first.function_id == 1
    assert first.priority == 0
    # No leftover stale duplicate should be poppable for the same function.
    q.enqueue(2, priority=1)
    second = await q.pop()
    assert second.function_id == 2


def test_lower_priority_number_after_inflight_does_not_reheap() -> None:
    """Once a function is in-flight, a repeat enqueue must not attempt to
    move it in the heap (it isn't there anymore) — only demand increments."""
    q = SummaryQueue(max_depth=10)
    q.enqueue(1, priority=2)

    async def _drain() -> None:
        await q.pop()

    asyncio.run(_drain())
    assert q.is_inflight(1)
    q.enqueue(1, priority=0)  # should not raise
    assert q._index[1].demand == 2


def test_release_drops_unstarted_item_at_zero_demand() -> None:
    q = SummaryQueue(max_depth=10)
    q.enqueue(1, priority=1)
    q.release(1)
    assert not q.is_queued(1)
    assert len(q) == 0


def test_release_does_not_drop_below_zero_demand() -> None:
    q = SummaryQueue(max_depth=10)
    q.enqueue(1, priority=1)
    q.enqueue(1, priority=1)
    q.release(1)
    assert q.is_queued(1)  # still one demand left
    q.release(1)
    assert not q.is_queued(1)


async def test_release_never_cancels_inflight_item() -> None:
    q = SummaryQueue(max_depth=10)
    q.enqueue(1, priority=1)
    item = await q.pop()
    assert q.is_inflight(1)
    q.release(1)
    # Still tracked as in-flight; the item is not removed while inflight.
    assert q.is_inflight(1)
    assert item.function_id == 1
    q.complete(1)
    assert not q.is_inflight(1)
    assert not q.is_queued(1)


def test_bounded_queue_evicts_lowest_priority_oldest_item() -> None:
    q = SummaryQueue(max_depth=2)
    q.enqueue(1, priority=3)
    q.enqueue(2, priority=2)
    # Third enqueue exceeds max_depth=2; should evict function 1 (lowest
    # priority number wins == most urgent, so priority=3 is least urgent).
    q.enqueue(3, priority=0)
    assert len(q) == 2
    assert not q.is_queued(1)
    assert q.is_queued(2)
    assert q.is_queued(3)


def test_eviction_raises_when_everything_is_inflight() -> None:
    q = SummaryQueue(max_depth=1)
    q.enqueue(1, priority=1)

    async def _drain() -> None:
        await q.pop()

    asyncio.run(_drain())
    assert q.is_inflight(1)
    with pytest.raises(QueueFullError):
        q.enqueue(2, priority=1)


def test_pause_sets_paused_until_in_the_future() -> None:
    q = SummaryQueue(max_depth=10)
    assert q.paused_until() is None
    q.pause(retry_after_seconds=60)
    assert q.paused_until() is not None


def test_pause_expires_after_retry_after() -> None:
    q = SummaryQueue(max_depth=10)
    q.pause(retry_after_seconds=0)
    assert q.paused_until() is None


async def test_pop_blocks_until_item_available() -> None:
    q = SummaryQueue(max_depth=10)

    async def _enqueue_later() -> None:
        await asyncio.sleep(0.01)
        q.enqueue(42, priority=0)

    task = asyncio.create_task(_enqueue_later())
    item = await q.pop()
    await task
    assert item.function_id == 42


async def test_pop_waits_for_an_active_rate_limit_pause() -> None:
    q = SummaryQueue(max_depth=10)
    q.enqueue(42, priority=0)
    q.pause(retry_after_seconds=0.02)

    item = await asyncio.wait_for(q.pop(), timeout=0.2)

    assert item.function_id == 42
    assert q.paused_until() is None


def test_snapshot_reflects_queued_and_inflight() -> None:
    q = SummaryQueue(max_depth=10)
    q.enqueue(1, priority=0)
    q.enqueue(2, priority=1)

    async def _drain_one() -> None:
        await q.pop()

    asyncio.run(_drain_one())
    snap = q.snapshot()
    queued_ids = {item.function_id for item in snap.queued}
    assert 1 in snap.inflight_function_ids
    assert 2 in queued_ids
    assert 1 not in queued_ids


def test_enqueue_rejects_out_of_range_priority() -> None:
    q = SummaryQueue(max_depth=10)
    with pytest.raises(ValueError, match="priority"):
        q.enqueue(1, priority=4)
    with pytest.raises(ValueError, match="priority"):
        q.enqueue(1, priority=-1)
