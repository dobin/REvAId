"""Closed enumerations shared by models, schemas, and DDL CHECK constraints.

One definition per closed set (TAD §1.2): these ``Literal`` aliases are the
single source of truth that the SQLAlchemy models, Pydantic schemas, and the
Alembic CHECK constraints all agree with. Widening one of these to add a new
value (e.g. ``EdgeKind`` gaining ``data_xref`` under A10) is a deliberate,
locatable change, not a silent default branch.
"""

from __future__ import annotations

from typing import Literal

FunctionKind = Literal["normal", "import", "thunk", "external", "placeholder"]
FUNCTION_KIND_VALUES: tuple[FunctionKind, ...] = (
    "normal",
    "import",
    "thunk",
    "external",
    "placeholder",
)

#: Kuna schema-v4 exports static control-flow and address-taken references in
#: addition to direct calls. Consumers that model only calls filter explicitly.
EdgeKind = Literal["call", "jump", "data"]
EDGE_KIND_VALUES: tuple[EdgeKind, ...] = ("call", "jump", "data")

#: The lifecycle includes `stale` for summaries invalidated by source changes.
SummaryStatus = Literal["none", "pending", "ready", "error", "stale"]
SUMMARY_STATUS_VALUES: tuple[SummaryStatus, ...] = (
    "none",
    "pending",
    "ready",
    "error",
    "stale",
)

UtilityOverride = Literal["always", "never"]
UTILITY_OVERRIDE_VALUES: tuple[UtilityOverride, ...] = ("always", "never")

#: The latest meaningful provider outcome for one configured adapter/model.
#: This is deliberately separate from ``Function.summary_status``: it powers
#: passive UI diagnostics and must not confuse a queued function with a
#: provider-connectivity assertion.
LlmWorkerOutcome = Literal["success", "failure", "rate_limited"]
LLM_WORKER_OUTCOME_VALUES: tuple[LlmWorkerOutcome, ...] = (
    "success",
    "failure",
    "rate_limited",
)
