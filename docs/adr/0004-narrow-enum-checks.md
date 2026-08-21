# ADR 0004 — Narrow CHECK constraints for closed enums that PRD calls "M0-only"

## Status

Accepted (locked for Milestone 1).

## Context

The PRD's Module-B enumeration table describes two columns whose *documented*
value set is wider than what M0 is ever supposed to write:

- `edges.kind`: "`call` (only value in M0). Reserved for `data_xref` /
  `string_ref` (A10)."
- `functions.summary_status`: B5 lists four values (`none`, `pending`,
  `ready`, `error`); the enumeration table lists a fifth, `stale`, which C10
  (a *Should*, not yet implemented) introduces.

TAD §3.3's own draft DDL permitted all of `edges.kind`'s eventual values
(`call`, `data_xref`, `string_ref`) from day one, and the TAD's own §1.2
argument for strict TypeScript enums — "adding `edges.kind = 'data_xref'`
should produce compile errors at every site that must handle it, not a
silent default branch" — argues for the opposite of what its own draft DDL
did.

## Decision

- `edges.kind` CHECK constraint in `0001_initial.py` is narrowed to
  `IN ('call')` only. Widening it to add `data_xref` / `string_ref` is a
  deliberate future migration (the A10 work item), which will also update
  `db/enums.py::EdgeKind` and `frontend/src/api/types.ts::EdgeKind`
  simultaneously — matching the TAD's own stated intent.
- `summary_status` CHECK constraint keeps **all five** values including
  `'stale'`, since it is already fully specified (Module-B enum table) even
  though M0's Musts never write it; C10 (Should) will start writing it
  without requiring a schema change.

## Consequences

- A future attempt to write `edges.kind = 'data_xref'` before the A10
  migration lands will fail loudly at the database layer, not silently
  succeed and confuse the canvas-edge derivation logic (which must never
  see anything but `call` edges in M0).
- `functions.summary_status = 'stale'` is already legal today, so C10 can be
  implemented without touching `0001_initial.py`.
