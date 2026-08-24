"""``LlmAdapter`` Protocol + raw DTOs + error taxonomy (TAD §6.3, AM1, AM2).

This is the contract a real LLM/agent integration must satisfy so I13 (real
adapters: litellm and opencode) can be implemented with zero changes to
``summarization/``, ``services/``, or the API surface. I7 ships only
:class:`~graphrev.adapters.llm.mock.MockLlmAdapter` behind this same Protocol.

Only this package's own ``__init__.py`` may import the concrete
``mock``/``litellm_adapter``/``opencode_adapter`` modules (enforced by the
"Only adapters/*/base may be imported outside their own package"
import-linter contract in ``pyproject.toml``) — every other caller
(``summarization``, ``services``, ...) depends on this module only.

Two deliberate amendments to the TAD's sketch of this Protocol, both recorded
in ``docs/specs/PLAN-I7-I8-I9-I13.md``:

- **AM1**: ``max_concurrency`` is part of the Protocol. The worker pool size
  is ``min(settings.summary_concurrency, adapter.max_concurrency)`` — a
  single-Ghidra-instance agent bridge (I13's opencode adapter) must declare
  ``1``; the TAD's flat ``summary_concurrency=4`` assumes every adapter is
  stateless, which is not true of an agent driving one loaded program.
- **AM2**: ``SummaryRequest`` carries ``binary_name``/``binary_version``/
  ``source_path`` from day one, even though the mock and litellm adapters
  ignore them. The opencode adapter (I13) needs to know which program is
  loaded in Ghidra; adding the fields now means I13 needs no protocol change,
  the same discipline the TAD already applies to ``notes``/``callee_summaries``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from graphrev.adapters.ghidra.base import RawParam


@dataclass(frozen=True, slots=True)
class SummaryRequest:
    """Everything an adapter needs to produce one function summary.

    ``callee_summaries`` is ``(name, summary_short)`` pairs (C9) — the
    already-generated short summaries of this function's callees, so the
    prompt/agent can build on prior work instead of re-deriving it.
    """

    address: int
    name: str
    parameters: tuple[RawParam, ...]
    code_c: str | None
    assembly: str | None
    analyst_name: str | None
    notes: str | None
    callee_summaries: tuple[tuple[str, str], ...]
    # AM2 — present from I7 so I13 needs no protocol change.
    binary_name: str
    binary_version: str
    source_path: str | None


@dataclass(frozen=True, slots=True)
class SummaryResult:
    """An adapter's successful output.

    ``summary_short`` MUST already fit one table row (C4) — the adapter owns
    clamping it, not the caller; the DB column is what the UI trusts.
    """

    summary_short: str
    summary_long: str
    model: str
    low_confidence: bool = False
    input_truncated: bool = False


@dataclass(frozen=True, slots=True)
class LlmHealth:
    """Adapter reachability, for ``GET /health`` (AM5)."""

    reachable: bool
    detail: str | None = None


# ---------------------------------------------------------------------------
# Error taxonomy (TAD §6.3) — the worker's entire retry policy is driven by
# these types and nothing else. Do not add ad-hoc exceptions elsewhere; map
# every provider-specific failure onto one of these.
# ---------------------------------------------------------------------------


class SummarizationError(Exception):
    """Base of the LLM error taxonomy. Never raised directly."""


class TransientProviderError(SummarizationError):
    """Retry x3 with exponential backoff + jitter."""


class RateLimitError(SummarizationError):
    """Pause the WHOLE queue until ``retry_after_seconds`` elapses.

    Rate-limit backoff is queue-wide, not per item (§5.1): the client sees one
    banner, not one error per in-flight request.
    """

    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AuthError(SummarizationError):
    """Fail fast, do not retry."""


class ContextTooLargeError(SummarizationError):
    """Fail with a specific code. The adapter owns truncation, not the caller."""


class PermanentProviderError(SummarizationError):
    """Fail. Cache nothing (C6) — an unparseable/garbage result must never be
    persisted as if it were a real summary."""


class LlmAdapter(Protocol):
    """LLM/agent access, abstracted behind an interface.

    Implementations: :class:`~graphrev.adapters.llm.mock.MockLlmAdapter` (I7),
    a litellm-backed adapter and an opencode-agent-backed adapter (both I13)
    — selected at runtime via :func:`graphrev.adapters.llm.create_adapter`,
    never imported directly outside this package.
    """

    @property
    def name(self) -> str:
        """Short identifier persisted to ``functions.summary_adapter`` (AM4)."""
        ...

    @property
    def max_concurrency(self) -> int:
        """Upper bound on concurrent :meth:`summarize` calls this adapter can
        safely sustain (AM1). The worker pool size is
        ``min(settings.summary_concurrency, adapter.max_concurrency)``."""
        ...

    async def summarize(self, req: SummaryRequest) -> SummaryResult:
        """Produce a summary, or raise a :class:`SummarizationError` subtype."""
        ...

    async def health(self) -> LlmHealth:
        """Cheap reachability check for ``GET /health`` (AM5)."""
        ...
