"""Viewer canvas provenance enums."""

from __future__ import annotations

from typing import Literal

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
