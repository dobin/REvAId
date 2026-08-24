# GraphRev glyph legend

Single source: `frontend/src/lib/glyphs.ts`. This document mirrors that file
so it can be linked from onboarding docs without importing TypeScript.

| Glyph | Meaning |
| --- | --- |
| ⤢ | Fan out — promote to canvas node (D8) |
| ◎ | Already on canvas — click to pan/focus (D9) |
| ◌ | Summary generating |
| ↻ | Recursive / part of a cycle |
| ▫ | Utility (high fan-in) — collapsed utility group (D34) |
| ≡ | Placeholder — outside the ingested module (D35a) |
| 📝 / ✎ | Has notes / renamed by analyst |
| ! | Error |
| ↺ | Retry a failed summary (I9) — distinct from ↻ (recursive) |
| ✨ | Marks LLM output (three-tier truthfulness, PRD §4.4) |
| ⋯ ✕ ⌄ ▾ ▸ ⇅ ⚙ 🎨 🔍 ✓ ⚠ | Card menu, close, collapse, expand, sort, settings, color, search, resolved, warning |

## M0 scope

M0 ships `⤢`, `◎`, `◌`, `▫`, `≡`, and the error `!`. `↻`, `📝`, and `✎` as
**row-level** glyphs arrive with D27 (Should) — except `↻` on the
self-recursion row, which D8/§5.1 require in M0 to explain why fan-out is
disabled there. `📝` and `✎` on the **card header** are M0 (D19, D20).

Note: the PRD's own M0-scoping sentence has a typo — it writes `⤲`
(U+2932) where every wireframe and the glyph table itself use `⤢` (U+2922)
for fan-out. This codebase uses `⤢`.
