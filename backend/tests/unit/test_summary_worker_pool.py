"""I7 exit test: `SummaryWorkerPool` never runs more than
`min(settings.summary_concurrency, adapter.max_concurrency)` summaries
concurrently, even when 50 requests arrive at once."""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graphrev.adapters.llm.base import LlmHealth, SummaryRequest, SummaryResult
from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Binary, Function
from graphrev.summarization.queue import SummaryQueue
from graphrev.summarization.worker import SummaryWorkerPool


class _ConcurrencyTrackingAdapter:
    """Records the high-water mark of concurrent `summarize()` calls."""

    def __init__(self, *, max_concurrency: int, hold_seconds: float = 0.05) -> None:
        self._max_concurrency = max_concurrency
        self._hold_seconds = hold_seconds
        self._current = 0
        self.high_water_mark = 0
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return "tracking-stub"

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    async def summarize(self, req: SummaryRequest) -> SummaryResult:
        async with self._lock:
            self._current += 1
            self.high_water_mark = max(self.high_water_mark, self._current)
        try:
            await asyncio.sleep(self._hold_seconds)
            return SummaryResult(summary_short="ok", summary_long="ok long", model="stub")
        finally:
            async with self._lock:
                self._current -= 1

    async def health(self) -> LlmHealth:
        return LlmHealth(reachable=True)


async def _make_functions(session: AsyncSession, count: int) -> list[Function]:
    now = utc_now_iso()
    binary = Binary(name="acme.exe", version="1.0", created_at=now, updated_at=now)
    session.add(binary)
    await session.flush()
    functions = []
    for i in range(count):
        fn = Function(
            binary_id=binary.id,
            address=0x1000 + i,
            name_ghidra=f"fn_{i}",
            code_c=f"int fn_{i}(void) {{ return {i}; }}",
            summary_status="pending",
            created_at=now,
            updated_at=now,
        )
        session.add(fn)
        functions.append(fn)
    await session.flush()
    await session.commit()
    return functions


async def test_worker_pool_never_exceeds_adapter_max_concurrency(
    session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    functions = await _make_functions(session, 50)
    queue = SummaryQueue(max_depth=100)
    for fn in functions:
        queue.enqueue(fn.id, priority=2)

    adapter = _ConcurrencyTrackingAdapter(max_concurrency=4)
    pool = SummaryWorkerPool(
        queue=queue,
        adapter=adapter,
        session_factory=session_factory,
        # Ask for far more than the adapter allows — AM1 must clamp it.
        concurrency=50,
    )
    assert pool.concurrency == 4

    pool.start()
    try:
        deadline = asyncio.get_event_loop().time() + 10
        while len(queue) > 0 or any(queue.is_inflight(fn.id) for fn in functions):
            if asyncio.get_event_loop().time() > deadline:
                raise AssertionError("worker pool did not drain the queue in time")
            await asyncio.sleep(0.02)
    finally:
        await pool.stop()

    assert adapter.high_water_mark <= 4
    assert adapter.high_water_mark > 1  # sanity: concurrency actually happened

    for fn in functions:
        await session.refresh(fn)
        assert fn.summary_status == "ready"
