# ADR 0001 — UI state lives on `view_nodes`, not on `functions`

## Status

Accepted (TAD v1.0, superseding `idea.md`'s original schema).

## Context

`idea.md`'s initial sketch put canvas position, visibility, and color directly
on the `functions` table — implying one binary has exactly one canvas layout.
The PRD (B1, B4, B4b) requires that an analyst work in **multiple independent
views** of the same binary (e.g. "crash path" vs. "parser internals"), each
with its own node positions, camera, and visibility, while analyst-authored
facts about a function (its rename, its notes) must be shared across all of
those views.

## Decision

- `views` is a first-class table: one binary has many views.
- `view_nodes` is a `(view_id, function_id)` join table holding everything
  that is a fact about *placement*: `visible`, `collapsed`, `color`, `pos_x`,
  `pos_y`, `pinned`, and the provenance triple (`origin_function_id`,
  `origin_kind`, `origin_implied`).
- `name_analyst`, `notes`, and `utility_override` stay on `functions` — they
  are facts about the function, not about a layout, and must be visible no
  matter which view the analyst is in (PRD J6).

## Consequences

- Switching views is cheap and never touches `functions`.
- Renaming a function or writing a note updates every view simultaneously,
  which is the correct behavior per the PRD.
- The schema has six tables instead of the naive five-column-on-`functions`
  design, but each table now has exactly one reason to change.
