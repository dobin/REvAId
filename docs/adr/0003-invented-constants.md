# ADR 0003 — Inventory of constants with no PRD basis

## Status

Accepted (informational — tracks what M1's V1–V3 validation should
re-examine with evidence from a real binary, per PRD §7.3).

## Context

The PRD names exactly five UI tuning constants in F1a: `TABLE_ROW_CAP` (16),
`CALLER_SUPPRESS_THRESHOLD` (32), `UTILITY_FANIN_THRESHOLD` (50),
`FAN_OUT_ALL_HARD_CAP` (50), `NODE_COUNT_SOFT_WARNING` (150). Every other
numeric value that appears in `Settings` (`backend/src/graphrev/core/config.py`)
is a TAD or implementation choice with no PRD-specified number. This ADR is
the single place that inventory is recorded, so it isn't mistaken for a
product decision later.

## Inventory

| Value | Field | Basis |
| --- | --- | --- |
| 380 px | `card_width_px` | PRD only says "card width is fixed" (AS23); no number given. |
| 4 | `summary_concurrency` | C5's "default assumption: 4". |
| 500 | `queue_max_depth` | C5 says "bounded FIFO queue"; no number given. |
| 128 | `name_analyst_max_length` | PRD §5.1 "stated assumption". |
| 250 ms | `node_patch_debounce_ms` | PRD requires debouncing (E3); no ms value given. |
| 400 ms | `view_patch_debounce_ms` | PRD requires debouncing (E3a); no ms value given. |
| 600 ms | `notes_autosave_debounce_ms` | PRD requires debouncing (D20); no ms value given. |
| 250 ms | `summary_demand_debounce_ms` | PRD §5.1 "fast-scroll guard"; no ms value given. |
| 15 s | `sse_keepalive_seconds` | No PRD value. |
| 256 | `sse_subscriber_queue_size` | No PRD value. |
| 5000 ms | `sqlite_busy_timeout_ms` | No PRD value. |
| `slate, red, amber, green, blue, violet, pink` | `NODE_COLOR_PALETTE` | D16 says "a small palette of named tokens"; only `red` is PRD-hinted (via J2's "attacker-reachable" example). |

## Consequences

- All of the above are `Settings` fields (or, for the palette, a module
  constant referenced only from `Settings`/the config DTO) — never a literal
  in a service, router, or frontend component.
- M1's V1–V3 exit criterion ("thresholds re-tuned by config alone, with
  evidence from a real binary") applies most directly to the F1a five; this
  table exists so a future contributor doesn't mistake e.g. `380` or `4` for
  a similarly PRD-mandated number.
