# ADR 0005 — Caller fan-out grows left via a `fanin` origin kind, not a direction column

## Status

Accepted (M0, migration 0004).

## Context

The PRD's §4.2 card wireframe always drew a `⤢` fan-out control on the
`CALLED BY` (caller) rows, and `D8` describes per-row fan-out generically. But
the M0 implementation only ever placed **callee** fan-outs: a caller row's
button was rendered enabled yet did nothing, because the neighbour table hard
-coded fan-out provenance to `direction === "callees" ? functionId : undefined`
(`NeighbourTable`, `UtilityGroup`). Analysts expect the graph to grow both
ways — a fanned-out callee to the right, a fanned-out caller to the left — so
they can walk up and down a call chain indefinitely from any card.

Canvas edges are derived **exclusively** from a node's provenance triple
(`origin_function_id`, `origin_kind`, `origin_implied`) — never from the
`edges` table (D8b, ADR 0001). ELK runs `layered` with `direction=RIGHT`,
which always lays an edge's source to the *left* of its target. So the
placement side of a new node is decided entirely by which way its provenance
edge points.

## Decision

Add a fourth `origin_kind` value, **`fanin`**, alongside `root` / `fanout` /
`callstack`. A `fanin` node is a fanned-out *caller*: it still records exactly
one origin (the card it was spawned from), but `deriveCanvasEdges` orients its
edge **node → origin** instead of the usual **origin → node**. Under
`direction=RIGHT` that places the caller to the left, with no change to the
ELK configuration or the `offsetPastObstacles` pass.

Concretely:

- `db/enums.py`: `OriginKind` and `ORIGIN_KIND_VALUES` gain `fanin`; a derived
  `PROVENANCE_ORIGIN_KIND_VALUES` (every kind except `root`) drives both the
  model CHECK constraint and the service-layer "requires an origin" rule, so
  the two can never drift.
- Migration `0004` widens the SQLite CHECK by rebuilding `view_nodes` with
  `batch_alter_table(copy_from=…, recreate="always")`. Safe here (unlike
  0002/0003) because `view_nodes` has no VIRTUAL generated column to trip the
  `INSERT INTO tmp SELECT …` copy.
- Frontend `deriveCanvasEdges` swaps source/target for `fanin`, keying the
  edge id on the owning `(origin, function)` pair so ids stay unique
  regardless of orientation.

## Alternatives rejected

1. **Rewrite the clicked card's own `origin_function_id`** to point at the new
   caller (making the *existing* card the ELK target). `origin_function_id` is
   a single nullable FK — one parent per node. Fanning out a **second** caller
   of the same card would overwrite the first, so the graph could never "grow
   infinitely left", and it would also destroy the clicked card's own
   provenance (a `root` would stop being a root).
2. **A separate `origin_direction` / `origin_side` column.** Creates a
   two-column state space in which most combinations are invalid (e.g. `root`
   with a direction), needs its own CHECK, and has to be threaded through
   `duplicate_view` and every DTO. A single widened enum has no invalid states.
3. **Orient from the `edges` table.** Forbidden by D8b — canvas edges come
   from provenance only.

## Consequences

- The layout subsystem stays completely direction-agnostic; growth direction
  is expressed once, in `deriveCanvasEdges`.
- The closed `OriginKind` union stays exhaustive, so per the TAD's §1.2 intent
  every `switch` over `origin_kind` fails to compile until it handles `fanin`.
- `fanin` is a provenance kind like `fanout`, so it requires a non-null
  `origin_function_id` (enforced in `canvas_service._validate_provenance`) and
  is copied verbatim by `duplicate_view`.
- Downgrading past 0004 fails loudly if any `fanin` row exists (the narrowed
  CHECK rejects it) — correct: those rows are unrepresentable in the old
  schema.
