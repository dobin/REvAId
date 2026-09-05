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

#: PRD Module-B: "`call` (only value in M0). Reserved for `data_xref` /
#: `string_ref` (A10)." Narrowed deliberately (docs/adr/0004) so a future
#: widening breaks the build at every site that must handle it.
EdgeKind = Literal["call"]
EDGE_KIND_VALUES: tuple[EdgeKind, ...] = ("call",)

#: Module-B enum table lists five values (adds "stale" beyond B5's four).
#: C10 (Should) is what introduces "stale"; kept from day one per docs/adr/0004.
SummaryStatus = Literal["none", "pending", "ready", "error", "stale"]
SUMMARY_STATUS_VALUES: tuple[SummaryStatus, ...] = (
    "none",
    "pending",
    "ready",
    "error",
    "stale",
)

#: `view_nodes.origin_kind`. `fanin` (added for leftward caller fan-out) is
#: like `fanout` but the derived canvas edge is oriented *from* the new node
#: *to* the card it was spawned from, so ELK (direction RIGHT) places it to
#: the left. Both `fanin` and `fanout` require a non-null `origin_function_id`
#: (see `PROVENANCE_ORIGIN_KIND_VALUES`).
OriginKind = Literal["root", "fanout", "callstack", "fanin"]
ORIGIN_KIND_VALUES: tuple[OriginKind, ...] = ("root", "fanout", "callstack", "fanin")

#: Every `origin_kind` except `root` — i.e. the kinds that require a non-null
#: `origin_function_id` (D8b). Derived from `ORIGIN_KIND_VALUES` so this list
#: can never drift out of sync when a new provenance kind is added.
PROVENANCE_ORIGIN_KIND_VALUES: tuple[OriginKind, ...] = tuple(
    k for k in ORIGIN_KIND_VALUES if k != "root"
)

UtilityOverride = Literal["always", "never"]
UTILITY_OVERRIDE_VALUES: tuple[UtilityOverride, ...] = ("always", "never")

UtilitySource = Literal["computed", "analyst"]

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
