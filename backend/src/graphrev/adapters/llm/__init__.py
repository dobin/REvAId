"""LLM adapter package.

This ``__init__.py`` is the **only** module allowed to import
``graphrev.adapters.llm.mock``/``.litellm_adapter``/``.opencode_adapter``
directly — every other caller (``summarization``, ``services``, ...) must go
through :func:`create_adapter` and the :mod:`graphrev.adapters.llm.base`
Protocol, per the ``import-linter`` "Only adapters/*/base may be imported
outside their own package" contract in ``pyproject.toml``.
"""

from __future__ import annotations

from graphrev.adapters.llm.base import LlmAdapter
from graphrev.core.config import LlmAdapterName, Settings


class LlmAdapterNotImplementedError(NotImplementedError):
    """Raised for an adapter name that has no implementation yet."""


def create_adapter(name: LlmAdapterName, settings: Settings, *, seed: int = 1337) -> LlmAdapter:
    """Select an `LlmAdapter` implementation by name (AM3).

    ``seed`` is only meaningful for ``"mock"``; real adapters ignore it.
    """
    if name == "mock":
        from graphrev.adapters.llm.mock import MockLlmAdapter

        return MockLlmAdapter(
            seed=seed,
            simulate_latency=settings.mock_llm_simulate_latency,
            min_latency_seconds=settings.mock_llm_min_latency_seconds,
            max_latency_seconds=settings.mock_llm_max_latency_seconds,
            failure_rate=settings.mock_llm_failure_rate,
        )
    if name == "litellm":
        raise LlmAdapterNotImplementedError(
            "The 'litellm' LLM adapter is not implemented until Increment I13. "
            "Use --llm-adapter mock for now."
        )
    if name == "opencode":
        raise LlmAdapterNotImplementedError(
            "The 'opencode' LLM adapter is not implemented until Increment I13. "
            "Use --llm-adapter mock for now."
        )
    raise LlmAdapterNotImplementedError(f"Unknown LLM adapter: {name!r}")


__all__ = [
    "LlmAdapter",
    "LlmAdapterNotImplementedError",
    "create_adapter",
]
