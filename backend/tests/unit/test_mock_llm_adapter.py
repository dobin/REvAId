"""C1: `MockLlmAdapter` determinism and error-injection behaviour."""

from __future__ import annotations

import pytest

from graphrev.adapters.llm.base import (
    RateLimitError,
    SummarizationError,
    SummaryRequest,
    TransientProviderError,
)
from graphrev.adapters.llm.mock import MockLlmAdapter


def _req(address: int = 0x401000, name: str = "do_thing") -> SummaryRequest:
    return SummaryRequest(
        address=address,
        name=name,
        parameters=(),
        code_c="int do_thing(void) { return 1; }",
        assembly="; disassembly",
        analyst_name=None,
        notes=None,
        callee_summaries=(),
        binary_name="acme.exe",
        binary_version="1.0",
        source_path=None,
    )


def test_name_and_max_concurrency() -> None:
    adapter = MockLlmAdapter(seed=1)
    assert adapter.name == "mock"
    assert adapter.max_concurrency == 4


async def test_health_is_always_reachable() -> None:
    adapter = MockLlmAdapter(seed=1)
    health = await adapter.health()
    assert health.reachable is True


async def test_same_seed_same_outcomes() -> None:
    """Two adapters built with the same seed must draw identical
    success/failure sequences given the same call sequence (C1)."""
    a1 = MockLlmAdapter(seed=42, simulate_latency=False)
    a2 = MockLlmAdapter(seed=42, simulate_latency=False)
    outcomes1 = []
    outcomes2 = []
    for i in range(30):
        req = _req(address=0x1000 + i)
        for adapter, outcomes in ((a1, outcomes1), (a2, outcomes2)):
            try:
                await adapter.summarize(req)
                outcomes.append("ok")
            except SummarizationError:
                outcomes.append("fail")
    assert outcomes1 == outcomes2
    # ~5% baseline failure rate should produce at least one failure or at
    # least mostly successes over 30 draws; assert it's not degenerate.
    assert "ok" in outcomes1


async def test_successful_summary_shape() -> None:
    adapter = MockLlmAdapter(seed=7, simulate_latency=False, failure_rate=0.0)
    result = await adapter.summarize(_req())
    assert result.model == "mock-llm-v1"
    assert result.summary_short
    assert len(result.summary_short) <= 120
    assert result.summary_long
    assert result.low_confidence is False


async def test_fail_on_forces_specific_error_type() -> None:
    adapter = MockLlmAdapter(
        seed=1,
        simulate_latency=False,
        failure_rate=0.0,
        fail_on={0x401000: TransientProviderError},
    )
    with pytest.raises(TransientProviderError):
        await adapter.summarize(_req(address=0x401000))
    # A different address is unaffected.
    result = await adapter.summarize(_req(address=0x402000, name="other"))
    assert result.summary_short


async def test_fail_on_rate_limit_carries_retry_after() -> None:
    adapter = MockLlmAdapter(
        seed=1,
        simulate_latency=False,
        failure_rate=0.0,
        fail_on={0x401000: RateLimitError},
    )
    with pytest.raises(RateLimitError) as exc_info:
        await adapter.summarize(_req(address=0x401000))
    assert exc_info.value.retry_after_seconds is not None


async def test_callee_summaries_reflected_in_long_summary() -> None:
    adapter = MockLlmAdapter(seed=1, simulate_latency=False, failure_rate=0.0)
    req = SummaryRequest(
        address=0x1234,
        name="parent_fn",
        parameters=(),
        code_c="int parent_fn(void) { return callee(); }",
        assembly=None,
        analyst_name=None,
        notes=None,
        callee_summaries=(("callee", "does a thing"),),
        binary_name="acme.exe",
        binary_version="1.0",
        source_path=None,
    )
    result = await adapter.summarize(req)
    assert "1 callee summary" in result.summary_long
