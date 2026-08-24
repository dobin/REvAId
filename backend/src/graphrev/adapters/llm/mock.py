"""Deterministic mock LLM adapter for I7 (C1).

:class:`MockLlmAdapter` is a *functional* requirement, not test scaffolding —
the whole I7 exit criteria (queueing, worker pool, retry/backoff behaviour)
depends on being able to control latency and failure without a real API key
or network access (TAD §6.3: "1-8 s latency, ~5% failures").

Failure injection is deterministic and explicitly controllable (rather than
purely random) so API/worker tests can assert exact retry/backoff behaviour:
a seeded PRNG drives the ~5% baseline failure rate, and callers may also pass
an explicit ``fail_on`` set of function addresses that always fail with a
chosen error type.
"""

from __future__ import annotations

import asyncio
import random

from graphrev.adapters.llm.base import (
    LlmHealth,
    RateLimitError,
    SummarizationError,
    SummaryRequest,
    SummaryResult,
    TransientProviderError,
)
from graphrev.adapters.mock_summaries import MOCK_SUMMARIES, fallback_summary

#: TAD §6.3 mock spec. Overridable via `Settings.mock_llm_*` (see
#: `adapters/llm/__init__.py::create_adapter`) so a demo/manual-UI-testing
#: session can dial latency down (or failures to zero) without editing this
#: module, while tests and normal `just dev` usage keep the original spec.
_MIN_LATENCY_SECONDS = 1.0
_MAX_LATENCY_SECONDS = 8.0
_BASELINE_FAILURE_RATE = 0.05

#: Deterministic minority of corpus-less functions rendered `low_confidence`
#: (reachable UI branch) — driven by the same seeded RNG draw as the
#: baseline failure check, so it stays reproducible per `seed`.
_LOW_CONFIDENCE_RATE = 0.15


class MockLlmAdapter:
    """Seeded, latency-simulating, occasionally-failing `LlmAdapter` (C1).

    Given the same ``seed``, the sequence of injected baseline failures is
    reproducible. ``fail_on`` additionally forces specific function addresses
    to fail with a given error, regardless of the seeded draw — used by tests
    that need a guaranteed failure (e.g. to exercise ``summary_status='error'``
    or rate-limit-pause behaviour) without depending on the random draw.
    """

    def __init__(
        self,
        *,
        seed: int = 1337,
        min_latency_seconds: float = _MIN_LATENCY_SECONDS,
        max_latency_seconds: float = _MAX_LATENCY_SECONDS,
        failure_rate: float = _BASELINE_FAILURE_RATE,
        fail_on: dict[int, type[SummarizationError]] | None = None,
        simulate_latency: bool = True,
    ) -> None:
        self._rng = random.Random(seed)
        self._min_latency = min_latency_seconds
        self._max_latency = max_latency_seconds
        self._failure_rate = failure_rate
        self._fail_on = dict(fail_on) if fail_on else {}
        self._simulate_latency = simulate_latency

    @property
    def name(self) -> str:
        return "mock"

    @property
    def max_concurrency(self) -> int:
        return 4

    async def summarize(self, req: SummaryRequest) -> SummaryResult:
        if self._simulate_latency:
            delay = self._rng.uniform(self._min_latency, self._max_latency)
            await asyncio.sleep(delay)

        forced = self._fail_on.get(req.address)
        if forced is not None:
            raise _instantiate(forced)

        if self._rng.random() < self._failure_rate:
            raise TransientProviderError(f"mock transient failure for {req.name!r}")

        low_confidence_draw = self._rng.random()

        display_name = req.analyst_name or req.name
        corpus_entry = MOCK_SUMMARIES.get(req.name)
        if corpus_entry is not None:
            summary_short, summary_long = corpus_entry
            low_confidence = False
        else:
            summary_short, summary_long = fallback_summary(
                display_name,
                req.address,
                has_code_c=req.code_c is not None,
                callee_count=len(req.callee_summaries),
            )
            low_confidence = low_confidence_draw < _LOW_CONFIDENCE_RATE

        return SummaryResult(
            summary_short=summary_short[:120],
            summary_long=summary_long,
            model="mock-llm-v1",
            low_confidence=low_confidence,
            input_truncated=False,
        )

    async def health(self) -> LlmHealth:
        return LlmHealth(reachable=True, detail=None)


def _instantiate(error_type: type[SummarizationError]) -> SummarizationError:
    if error_type is RateLimitError:
        return RateLimitError("mock forced rate limit", retry_after_seconds=0.01)
    return error_type("mock forced failure")
