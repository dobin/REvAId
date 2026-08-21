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

OriginKind = Literal["root", "fanout", "callstack"]
ORIGIN_KIND_VALUES: tuple[OriginKind, ...] = ("root", "fanout", "callstack")

UtilityOverride = Literal["always", "never"]
UTILITY_OVERRIDE_VALUES: tuple[UtilityOverride, ...] = ("always", "never")

UtilitySource = Literal["computed", "analyst"]
