"""The summarization worker pool (TAD §2.6, C5/C5a/C6, AM1).

``SummaryWorkerPool`` owns ``N = min(settings.summary_concurrency,
adapter.max_concurrency)`` asyncio tasks (AM1 — a single-Ghidra-instance agent
adapter must not get four parallel workers). Each task loops:
``pop -> load context -> adapter.summarize() -> persist -> repeat``.

Retry policy is driven entirely by the error taxonomy in ``adapters/llm/base.py``:

- ``TransientProviderError``: retried up to 3 times total, with exponential
  backoff + jitter, before the item is recorded as ``summary_status='error'``.
- ``RateLimitError``: pauses the *whole* queue (`SummaryQueue.pause`) and
  requeues this item at its original priority — no card-level error, no
  "used up" retry count for this function.
- ``AuthError`` / ``ContextTooLargeError`` / ``PermanentProviderError``: fail
  immediately, ``summary_status='error'``, cache nothing (C6).
- Anything else (including a hang) is bounded by ``asyncio.timeout`` so one
  stuck call can never wedge a worker slot permanently.

Event publication (SSE, I8) is deliberately **not** part of this module yet —
it is added when ``events/bus.py`` exists, without changing this module's own
persistence logic (an ``on_result`` hook keeps that addition additive).
"""

from __future__ import annotations

import asyncio
import contextlib
import random
from collections.abc import Awaitable
from typing import Protocol, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graphrev.adapters.llm.base import (
    AuthError,
    ContextTooLargeError,
    LlmAdapter,
    PermanentProviderError,
    RateLimitError,
    SummarizationError,
    SummaryResult,
    TransientProviderError,
)
from graphrev.core.clock import utc_now_iso
from graphrev.core.hashing import summary_input_hash
from graphrev.core.logging import get_logger, log_event
from graphrev.db.uow import unit_of_work
from graphrev.summarization.context import build_summary_request
from graphrev.summarization.queue import QueueItem, SummaryQueue

logger = get_logger(__name__)

#: TAD §6.3 error taxonomy: retry a TransientProviderError up to 3 times
#: total before giving up.
_MAX_TRANSIENT_RETRIES = 3
_BASE_BACKOFF_SECONDS = 0.5
_MAX_BACKOFF_SECONDS = 8.0
#: Bound every adapter call so a hung/misbehaving adapter cannot wedge a
#: worker slot forever (relevant once agent-based adapters exist in I13).
_SUMMARIZE_TIMEOUT_SECONDS = 120.0


class ResultListener(Protocol):
    """I8's SSE publishing hook. Carries everything `SummaryEventDto` needs
    so the listener never has to re-read the DB row it was just told about
    (`main.py` wires this to `EventBus.publish` via a small adapter
    function, keeping this module free of any `events`/`schemas` import)."""

    def __call__(
        self,
        *,
        function_id: int,
        binary_id: int,
        summary_status: str,
        summary_short: str | None,
        summary_model: str | None,
        low_confidence: bool,
        generated_at: str | None,
        error_code: str | None,
    ) -> Awaitable[None]: ...


async def _persist_success(
    session: AsyncSession,
    *,
    function_id: int,
    result: SummaryResult,
    adapter_name: str,
    input_hash: str,
    generated_at: str,
) -> int:
    """Write a successful result; returns the function's `binary_id` (for
    event publication) via a single UPDATE...RETURNING."""
    row = await session.execute(
        text(
            """
            UPDATE functions
            SET summary_short = :summary_short,
                summary_long = :summary_long,
                name_llm = :name_llm,
                summary_status = 'ready',
                summary_model = :model,
                summary_adapter = :adapter,
                summary_error_code = NULL,
                summary_low_confidence = :low_confidence,
                summary_generated_at = :generated_at,
                summary_input_hash = :input_hash,
                updated_at = :generated_at
            WHERE id = :function_id
            RETURNING binary_id
            """
        ),
        {
            "summary_short": result.summary_short,
            "summary_long": result.summary_long,
            "name_llm": result.name_llm,
            "model": result.model,
            "adapter": adapter_name,
            "low_confidence": result.low_confidence,
            "generated_at": generated_at,
            "input_hash": input_hash,
            "function_id": function_id,
        },
    )
    return cast(int, row.scalar_one())


async def _persist_failure(
    session: AsyncSession, *, function_id: int, error_code: str
) -> int | None:
    """Write a failed result (C6 — no summary_* fields touched besides status
    and error_code). Returns `binary_id`, or `None` if the function vanished
    (deleted mid-flight)."""
    row = await session.execute(
        text(
            """
            UPDATE functions
            SET summary_status = 'error',
                summary_error_code = :error_code,
                updated_at = :updated_at
            WHERE id = :function_id
            RETURNING binary_id
            """
        ),
        {
            "error_code": error_code,
            "updated_at": utc_now_iso(),
            "function_id": function_id,
        },
    )
    return row.scalar_one_or_none()


def _error_code_for(exc: SummarizationError) -> str:
    """Map an exception type onto `ErrorCode` string values (E4)."""
    if isinstance(exc, RateLimitError):
        return "SUMMARY_RATE_LIMITED"
    # I13: adapters may pin a specific code (e.g. the opencode adapter's
    # GhidraProgramMismatchError -> GHIDRA_PROGRAM_MISMATCH).
    pinned = getattr(exc, "error_code", None)
    if isinstance(pinned, str):
        return pinned
    return "SUMMARY_PROVIDER_ERROR"


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff + jitter, capped, for `TransientProviderError`."""
    base = min(_MAX_BACKOFF_SECONDS, _BASE_BACKOFF_SECONDS * (2**attempt))
    return float(base * (0.5 + random.random()))


class SummaryWorkerPool:
    """Owns the N summarization worker tasks and their lifecycle.

    Not itself the queue or the adapter — those are constructed by the
    caller (``main.py`` lifespan / ``api/deps.py``) and passed in, so tests
    can drive a single :func:`_run_one_item` cycle without a whole pool.
    """

    def __init__(
        self,
        *,
        queue: SummaryQueue,
        adapter: LlmAdapter,
        session_factory: async_sessionmaker[AsyncSession],
        concurrency: int,
        result_listener: ResultListener | None = None,
    ) -> None:
        self._queue = queue
        self._adapter = adapter
        self._session_factory = session_factory
        #: AM1 — never exceed what the adapter itself declares safe.
        self._concurrency = max(1, min(concurrency, adapter.max_concurrency))
        self._result_listener = result_listener
        self._tasks: list[asyncio.Task[None]] = []

    @property
    def concurrency(self) -> int:
        return self._concurrency

    def start(self) -> None:
        if self._tasks:
            raise RuntimeError("SummaryWorkerPool already started")
        self._tasks = [
            asyncio.create_task(self._run_loop(worker_index=i), name=f"summary-worker-{i}")
            for i in range(self._concurrency)
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks = []

    async def _run_loop(self, *, worker_index: int) -> None:
        while True:
            item = await self._queue.pop()
            requeued = False
            try:
                requeued = await self._process_item(item, worker_index=worker_index)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - defensive; a worker must never die
                logger.exception("summary_worker.unexpected_error", function_id=item.function_id)
            finally:
                if not requeued:
                    self._queue.complete(item.function_id)

    async def _process_item(self, item: QueueItem, *, worker_index: int) -> bool:
        return await run_one_item(
            item,
            queue=self._queue,
            adapter=self._adapter,
            session_factory=self._session_factory,
            result_listener=self._result_listener,
        )


async def run_one_item(
    item: QueueItem,
    *,
    queue: SummaryQueue,
    adapter: LlmAdapter,
    session_factory: async_sessionmaker[AsyncSession],
    result_listener: ResultListener | None = None,
) -> bool:
    """Process exactly one popped :class:`QueueItem` to completion (success,
    permanent failure, or a queue-wide-pause requeue). Split out from
    :class:`SummaryWorkerPool` so tests can drive it directly without a pool
    of background tasks.

    Returns ``True`` if the item was requeued after a `RateLimitError` (the
    caller must NOT call `queue.complete()` in that case — the item is back
    on the queue, not finished), ``False`` otherwise."""
    function_id = item.function_id

    async with session_factory() as session:
        req = await build_summary_request(session, function_id=function_id)

    input_hash = summary_input_hash(
        name=req.analyst_name or req.name,
        code_c=req.code_c,
        assembly=req.assembly,
        notes=req.notes,
    )

    attempt = 0
    while True:
        try:
            async with asyncio.timeout(_SUMMARIZE_TIMEOUT_SECONDS):
                result = await adapter.summarize(req)
        except TimeoutError:
            attempt += 1
            if attempt >= _MAX_TRANSIENT_RETRIES:
                await _fail(
                    session_factory,
                    function_id=function_id,
                    error_code="SUMMARY_PROVIDER_ERROR",
                    result_listener=result_listener,
                    adapter_name=adapter.name,
                    reason=f"timeout after {_SUMMARIZE_TIMEOUT_SECONDS}s x{attempt}",
                )
                return False
            await asyncio.sleep(_backoff_seconds(attempt))
            continue
        except RateLimitError as exc:
            queue.pause(exc.retry_after_seconds or _BASE_BACKOFF_SECONDS)
            log_event(
                logger,
                "summary_worker.rate_limited",
                function_id=function_id,
                adapter=adapter.name,
                outcome="rate_limited",
            )
            # Requeue at the item's original priority, preserving its demand
            # refcount; do not consume a retry attempt or mark the function
            # as errored — the whole queue is paused, not this one function.
            queue.requeue_inflight(function_id, item.priority)
            return True
        except TransientProviderError as exc:
            attempt += 1
            if attempt >= _MAX_TRANSIENT_RETRIES:
                await _fail(
                    session_factory,
                    function_id=function_id,
                    error_code="SUMMARY_PROVIDER_ERROR",
                    result_listener=result_listener,
                    adapter_name=adapter.name,
                    reason=f"{type(exc).__name__}: {exc}",
                )
                return False
            await asyncio.sleep(_backoff_seconds(attempt))
            continue
        except (AuthError, ContextTooLargeError, PermanentProviderError) as exc:
            await _fail(
                session_factory,
                function_id=function_id,
                error_code=_error_code_for(exc),
                result_listener=result_listener,
                adapter_name=adapter.name,
                reason=f"{type(exc).__name__}: {exc}",
            )
            return False
        else:
            await _succeed(
                session_factory,
                function_id=function_id,
                result=result,
                input_hash=input_hash,
                adapter_name=adapter.name,
                result_listener=result_listener,
            )
            return False


async def _succeed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    function_id: int,
    result: SummaryResult,
    input_hash: str,
    adapter_name: str,
    result_listener: ResultListener | None,
) -> None:
    generated_at = utc_now_iso()
    async with unit_of_work(session_factory) as session:
        binary_id = await _persist_success(
            session,
            function_id=function_id,
            result=result,
            adapter_name=adapter_name,
            input_hash=input_hash,
            generated_at=generated_at,
        )
    log_event(
        logger,
        "summary_worker.completed",
        function_id=function_id,
        binary_id=binary_id,
        adapter=adapter_name,
        model=result.model,
        outcome="success",
    )
    if result_listener is not None:
        await result_listener(
            function_id=function_id,
            binary_id=binary_id,
            summary_status="ready",
            summary_short=result.summary_short,
            summary_model=result.model,
            low_confidence=result.low_confidence,
            generated_at=generated_at,
            error_code=None,
        )


async def _fail(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    function_id: int,
    error_code: str,
    result_listener: ResultListener | None,
    adapter_name: str | None = None,
    reason: str | None = None,
) -> None:
    async with unit_of_work(session_factory) as session:
        binary_id = await _persist_failure(session, function_id=function_id, error_code=error_code)
    log_event(
        logger,
        "summary_worker.failed",
        function_id=function_id,
        binary_id=binary_id,
        adapter=adapter_name,
        outcome="error",
        error_code=error_code,
        # The provider's own message. Without it a `SUMMARY_PROVIDER_ERROR`
        # is undiagnosable from logs alone (which cost a debugging session
        # when DeepseSeek-via-OpenRouter returned fenced JSON).
        reason=reason,
    )
    if result_listener is not None and binary_id is not None:
        await result_listener(
            function_id=function_id,
            binary_id=binary_id,
            summary_status="error",
            summary_short=None,
            summary_model=None,
            low_confidence=False,
            generated_at=None,
            error_code=error_code,
        )
