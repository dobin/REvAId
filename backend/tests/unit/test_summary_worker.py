"""I7 exit criteria for the worker: success persists `ready`, permanent
failure persists `error` (caching nothing else, C6), transient failure
retries then fails, and a rate limit pauses the whole queue and requeues
the item without ever marking it errored."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graphrev.adapters.llm.base import (
    AuthError,
    LlmHealth,
    RateLimitError,
    SummaryRequest,
    SummaryResult,
    TransientProviderError,
)
from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Binary, Function, LlmWorkerStatus
from graphrev.summarization import worker as worker_module
from graphrev.summarization.queue import SummaryQueue
from graphrev.summarization.worker import run_one_item


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Collapse the worker's real exponential backoff sleeps to zero.

    The transient-retry tests would otherwise block for ~1.5-3s of real
    wall time each on `asyncio.sleep(_backoff_seconds(attempt))`.
    """
    monkeypatch.setattr(worker_module, "_backoff_seconds", lambda attempt: 0)


class _StubAdapter:
    """A minimal `LlmAdapter` double whose behaviour is scripted per call."""

    def __init__(self, outcomes: list[Exception | SummaryResult]) -> None:
        self._outcomes = list(outcomes)
        self.calls = 0

    @property
    def name(self) -> str:
        return "stub"

    @property
    def max_concurrency(self) -> int:
        return 4

    async def summarize(self, req: SummaryRequest) -> SummaryResult:
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


async def _make_function(
    session: AsyncSession, *, name: str = "do_thing", binary_name: str = "acme.exe"
) -> Function:
    now = utc_now_iso()
    binary = Binary(name=binary_name, version="1.0", created_at=now, updated_at=now)
    session.add(binary)
    await session.flush()
    fn = Function(
        binary_id=binary.id,
        address=0x1000,
        name_ghidra=name,
        code_c="int do_thing(void) { return 1; }",
        summary_status="pending",
        created_at=now,
        updated_at=now,
    )
    session.add(fn)
    await session.flush()
    await session.commit()
    return fn


async def test_successful_summarize_persists_ready_status(
    session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fn = await _make_function(session)
    queue = SummaryQueue(max_depth=10)
    item = queue.enqueue(fn.id, priority=0)
    await queue.pop()

    adapter = _StubAdapter(
        [SummaryResult(summary_short="short", summary_long="long", model="stub-v1")]
    )
    requeued = await run_one_item(
        item, queue=queue, adapter=adapter, session_factory=session_factory
    )
    assert requeued is False

    await session.refresh(fn)
    assert fn.summary_status == "ready"
    assert fn.summary_short == "short"
    assert fn.summary_long == "long"
    assert fn.summary_model == "stub-v1"
    assert fn.summary_input_hash is not None
    status = await session.get(LlmWorkerStatus, 1)
    assert status is not None
    assert status.outcome == "success"
    assert status.adapter == "stub"
    assert status.model == "stub"


async def test_successful_summarize_logs_non_null_duration_and_attempt_count(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fn = await _make_function(session)
    queue = SummaryQueue(max_depth=10)
    item = queue.enqueue(fn.id, priority=0)
    await queue.pop()
    events: list[dict[str, object]] = []

    def _record_event(*args: object, **kwargs: object) -> None:
        events.append(kwargs)

    monkeypatch.setattr(worker_module, "log_event", _record_event)
    adapter = _StubAdapter(
        [SummaryResult(summary_short="short", summary_long="long", model="stub-v1")]
    )

    await run_one_item(item, queue=queue, adapter=adapter, session_factory=session_factory)

    completed = next(event for event in events if event["outcome"] == "success")
    assert isinstance(completed["duration_ms"], float)
    assert completed["duration_ms"] >= 0
    assert completed["attempt_count"] == 1


async def test_successful_summarize_persists_name_llm(
    session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """C13 auto-display: the adapter's proposed name is persisted alongside
    the summary, and participates in the display precedence (analyst beats
    LLM beats Ghidra) without overwriting either stored name."""
    fn = await _make_function(session, name="FUN_00001000")
    queue = SummaryQueue(max_depth=10)
    item = queue.enqueue(fn.id, priority=0)
    await queue.pop()

    adapter = _StubAdapter(
        [
            SummaryResult(
                summary_short="short",
                summary_long="long",
                model="stub-v1",
                name_llm="parse_header",
            )
        ]
    )
    await run_one_item(item, queue=queue, adapter=adapter, session_factory=session_factory)

    await session.refresh(fn)
    assert fn.name_llm == "parse_header"
    # Neither stored name is overwritten.
    assert fn.name_ghidra == "FUN_00001000"
    assert fn.name_analyst is None


async def test_successful_summarize_without_name_llm_leaves_column_null(
    session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """An adapter that omits `name_llm` (older adapter, model returned null)
    must not fail the persist — the column simply stays NULL and the Ghidra
    name remains the display name."""
    fn = await _make_function(session, name="FUN_00001000")
    queue = SummaryQueue(max_depth=10)
    item = queue.enqueue(fn.id, priority=0)
    await queue.pop()

    adapter = _StubAdapter(
        [SummaryResult(summary_short="short", summary_long="long", model="stub-v1")]
    )
    await run_one_item(item, queue=queue, adapter=adapter, session_factory=session_factory)

    await session.refresh(fn)
    assert fn.summary_status == "ready"
    assert fn.name_llm is None


async def test_permanent_failure_persists_error_and_caches_nothing(
    session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fn = await _make_function(session)
    queue = SummaryQueue(max_depth=10)
    item = queue.enqueue(fn.id, priority=0)
    await queue.pop()

    adapter = _StubAdapter([AuthError("bad key")])
    requeued = await run_one_item(
        item, queue=queue, adapter=adapter, session_factory=session_factory
    )
    assert requeued is False

    await session.refresh(fn)
    assert fn.summary_status == "error"
    assert fn.summary_error_code == "SUMMARY_PROVIDER_ERROR"
    assert fn.summary_short is None  # C6: nothing cached on failure
    status = await session.get(LlmWorkerStatus, 1)
    assert status is not None
    assert status.outcome == "failure"
    assert status.error_code == "SUMMARY_PROVIDER_ERROR"


async def test_pinned_error_code_is_persisted(
    session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """I13 §6.6: the opencode adapter's filename guard must surface as
    GHIDRA_PROGRAM_MISMATCH (nothing cached) — the worker honours an
    adapter-pinned `error_code` attribute."""
    fn = await _make_function(session)
    queue = SummaryQueue(max_depth=10)
    item = queue.enqueue(fn.id, priority=0)
    await queue.pop()

    from graphrev.adapters.llm.base import GhidraProgramMismatchError

    adapter = _StubAdapter(
        [GhidraProgramMismatchError("agent summarised other.exe, wanted demo.exe")]
    )
    requeued = await run_one_item(
        item, queue=queue, adapter=adapter, session_factory=session_factory
    )
    assert requeued is False

    await session.refresh(fn)
    assert fn.summary_status == "error"
    assert fn.summary_error_code == "GHIDRA_PROGRAM_MISMATCH"
    assert fn.summary_short is None  # nothing written to summary_*


async def test_transient_failure_retries_then_fails(
    session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fn = await _make_function(session)
    queue = SummaryQueue(max_depth=10)
    item = queue.enqueue(fn.id, priority=0)
    await queue.pop()

    adapter = _StubAdapter(
        [
            TransientProviderError("try again"),
            TransientProviderError("try again"),
            TransientProviderError("try again"),
        ]
    )
    requeued = await run_one_item(
        item, queue=queue, adapter=adapter, session_factory=session_factory
    )
    assert requeued is False
    assert adapter.calls == 3  # exactly _MAX_TRANSIENT_RETRIES attempts

    await session.refresh(fn)
    assert fn.summary_status == "error"
    assert fn.summary_error_code == "SUMMARY_PROVIDER_ERROR"


async def test_transient_failure_recovers_on_retry(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fn = await _make_function(session)
    queue = SummaryQueue(max_depth=10)
    item = queue.enqueue(fn.id, priority=0)
    await queue.pop()
    events: list[dict[str, object]] = []

    def _record_event(*args: object, **kwargs: object) -> None:
        events.append(kwargs)

    monkeypatch.setattr(worker_module, "log_event", _record_event)

    adapter = _StubAdapter(
        [
            TransientProviderError("try again"),
            SummaryResult(summary_short="ok", summary_long="ok long", model="stub-v1"),
        ]
    )
    requeued = await run_one_item(
        item, queue=queue, adapter=adapter, session_factory=session_factory
    )
    assert requeued is False

    await session.refresh(fn)
    assert fn.summary_status == "ready"
    assert fn.summary_short == "ok"
    retrying = next(event for event in events if event["outcome"] == "retrying")
    assert retrying["attempt_count"] == 1
    assert retrying["next_attempt_count"] == 2
    assert retrying["max_attempts"] == 3
    assert retrying["error_type"] == "TransientProviderError"
    assert retrying["reason"] == "try again"
    assert retrying["retry_delay_seconds"] == 0


async def test_rate_limit_pauses_queue_and_requeues_without_erroring(
    session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    fn = await _make_function(session)
    queue = SummaryQueue(max_depth=10)
    item = queue.enqueue(fn.id, priority=1)
    await queue.pop()
    assert queue.is_inflight(fn.id)

    adapter = _StubAdapter([RateLimitError("slow down", retry_after_seconds=30)])
    requeued = await run_one_item(
        item, queue=queue, adapter=adapter, session_factory=session_factory
    )
    assert requeued is True

    # The queue is paused and the item is back on the queue, not errored.
    assert queue.paused_until() is not None
    assert not queue.is_inflight(fn.id)
    assert queue.is_queued(fn.id)

    await session.refresh(fn)
    assert fn.summary_status == "pending"  # untouched by the worker on rate limit
    assert fn.summary_error_code is None
    status = await session.get(LlmWorkerStatus, 1)
    assert status is not None
    assert status.outcome == "rate_limited"
    assert status.error_code == "SUMMARY_RATE_LIMITED"


async def test_rate_limits_back_off_then_terminally_cancel_all_queued_requests(
    session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """An unknown provider limit gets 30s, 60s, 120s, then stops retrying.

    Clearing the monotonic deadline in this unit test simulates each pause
    elapsing without making the test wait three and a half minutes.
    """
    fn = await _make_function(session)
    second_fn = await _make_function(session, name="other_thing", binary_name="other.exe")
    queue = SummaryQueue(max_depth=10)
    item = queue.enqueue(fn.id, priority=1)
    queue.enqueue(second_fn.id, priority=1)
    await queue.pop()
    adapter = _StubAdapter(
        [
            RateLimitError("slow down"),
            RateLimitError("slow down"),
            RateLimitError("slow down"),
            RateLimitError("slow down"),
        ]
    )

    expected_backoffs = (30.0, 60.0, 120.0)
    for expected_backoff in expected_backoffs:
        before = worker_module.time.monotonic()
        assert await run_one_item(
            item, queue=queue, adapter=adapter, session_factory=session_factory
        )
        paused_until = queue.paused_until()
        assert paused_until is not None
        assert paused_until - before == pytest.approx(expected_backoff, abs=0.1)
        queue._paused_until = None
        item = await queue.pop()

    assert not await run_one_item(
        item, queue=queue, adapter=adapter, session_factory=session_factory
    )
    assert adapter.calls == 4
    await session.refresh(fn)
    assert fn.summary_status == "error"
    assert fn.summary_error_code == "SUMMARY_RATE_LIMITED"
    await session.refresh(second_fn)
    assert second_fn.summary_status == "error"
    assert second_fn.summary_error_code == "SUMMARY_RATE_LIMITED"
    assert not queue.is_queued(fn.id)


async def test_adapter_health_reports_reachable() -> None:
    class _AlwaysUp:
        @property
        def name(self) -> str:
            return "stub"

        @property
        def max_concurrency(self) -> int:
            return 1

        async def summarize(self, req: SummaryRequest) -> SummaryResult:
            raise NotImplementedError

        async def health(self) -> LlmHealth:
            return LlmHealth(reachable=True)

    health = await _AlwaysUp().health()
    assert health.reachable is True
