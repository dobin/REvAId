"""`adapters/llm/__init__.py::create_adapter` — settings plumbing for the mock
adapter's latency/failure knobs (demo tuning; see README "Configuration")."""

from __future__ import annotations

import pytest

from graphrev.adapters.llm import create_adapter
from graphrev.adapters.llm.mock import MockLlmAdapter
from graphrev.core.config import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[arg-type]


def test_create_adapter_mock_returns_mock_llm_adapter() -> None:
    adapter = create_adapter("mock", _settings())
    assert isinstance(adapter, MockLlmAdapter)
    assert adapter.name == "mock"


def test_create_adapter_honours_simulate_latency_setting() -> None:
    settings = _settings(mock_llm_simulate_latency=False)
    adapter = create_adapter("mock", settings)
    assert adapter._simulate_latency is False


def test_create_adapter_honours_latency_bounds_and_failure_rate() -> None:
    settings = _settings(
        mock_llm_simulate_latency=True,
        mock_llm_min_latency_seconds=0.1,
        mock_llm_max_latency_seconds=0.2,
        mock_llm_failure_rate=0.0,
    )
    adapter = create_adapter("mock", settings)
    assert adapter._min_latency == pytest.approx(0.1)
    assert adapter._max_latency == pytest.approx(0.2)
    assert adapter._failure_rate == pytest.approx(0.0)


def test_default_settings_disable_latency_simulation() -> None:
    """Demo/test-friendliness default (per README): `just test` and everyday
    `just dev` must not pay the 1-8s TAD-spec latency unless a developer
    opts in via `GRAPHREV_MOCK_LLM_SIMULATE_LATENCY=true`."""
    settings = _settings()
    assert settings.mock_llm_simulate_latency is False
    adapter = create_adapter("mock", settings)
    assert adapter._simulate_latency is False


def test_create_adapter_litellm_returns_litellm_adapter() -> None:
    from graphrev.adapters.llm.litellm_adapter import LiteLlmAdapter

    adapter = create_adapter("litellm", _settings())
    assert isinstance(adapter, LiteLlmAdapter)
    assert adapter.name == "litellm"
    assert adapter.max_concurrency == _settings().summary_concurrency


def test_create_adapter_opencode_returns_opencode_adapter() -> None:
    from graphrev.adapters.llm.opencode_adapter import OpenCodeAdapter

    adapter = create_adapter("opencode", _settings())
    assert isinstance(adapter, OpenCodeAdapter)
    assert adapter.name == "opencode"
    # AM1: one Ghidra program, one bridge — the pool must never run parallel
    # agents against a single Ghidra instance.
    assert adapter.max_concurrency == 1
