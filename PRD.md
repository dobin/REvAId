# GraphRev — Product Requirements Document

| Field | Value |
| --- | --- |
| Product name | GraphRev (working title) |
| Document owner | Principal PM |
| Version | 0.8 — bidirectional fan-out (`fanin`, caller fan-out grows left); TAD-readiness pass in 0.7 (see §9 changelog) |
| Date | 2026-08-22 |
| Status | Pre-implementation. Ghidra bridge and LLM agent are **mocked** in v0. |

---

## 1. Executive Summary & Core Value Proposition

### 1.1 Problem

Reverse engineers spend the majority of their time on *orientation*, not on *insight*. When landing in an unfamiliar binary — from a crash callstack, a CVE writeup, or a suspicious import — the analyst must repeatedly:

1. Jump to a function in Ghidra.
2. Read 200 lines of decompiled C full of `FUN_00401a20`, `uVar7`, and casts.
3. Build a mental model of "what does this actually do".
4. Follow one xref, and lose the mental model of the previous frame.

Ghidra's own graph views operate at the **basic block / control-flow** level, which is too fine-grained for orientation, and its function call tree is a bare name list with no semantics. The result: high cognitive load, poor shareability, and slow ramp-up on new binaries.

### 1.2 Solution

GraphRev is a web application that renders a **semantic function graph** of a binary. Each node is a *function card* showing the function name, signature, and two LLM-generated summaries (a short gist and a detailed behavioral description) instead of assembly or decompiled C.

Crucially, each card also carries its own **callee table and caller table** — a compact list of every function it calls and every function that calls it, each row showing the neighbour's name plus its short summary. The analyst reads these tables to decide where to go next, then clicks a **fan-out** button on the specific rows worth investigating. Nothing is promoted to the canvas automatically.

This makes the card, not the graph, the unit of exploration: the analyst always sees the *complete* local neighbourhood in readable list form, while the canvas holds only the handful of functions they deliberately chose to place there.

### 1.3 Core Value Proposition

> **Understand what a binary *does* before you read a single line of disassembly.**

Three pillars:

| Pillar | Statement |
| --- | --- |
| **Semantic abstraction** | Replace pseudocode with natural-language meaning at the function level — the level at which humans reason about programs. |
| **Deliberate topology** | The full local neighbourhood is always legible *inside* the card as a summarised table; only explicitly chosen functions become canvas nodes. The graph never grows behind the analyst's back. |
| **Durable, cached artifact** | Summaries, plus per-view layout, colors, visibility, analyst names and notes persist in SQLite, so a **view** becomes a reusable, shareable analysis artifact rather than a throwaway canvas. |

### 1.4 Success Metrics

Two tiers, separated by how they are measured. Since GraphRev is a locally-run single-user tool with **no telemetry** (see AS13), the outcome metrics are validated by *qualitative self-assessment / hallway testing*, not instrumentation. Only the engineering metrics are measured automatically from the DB and server logs.

**Tier 1 — Outcome (qualitative, judged by the user after real analysis sessions)**

| Question | Bar for "this product works" |
| --- | --- |
| After pasting an unknown callstack, do I know which frame to dig into first? | Yes, within one screen-read, without opening Ghidra. |
| Are the short summaries accurate enough that I trust them for navigation? | I rarely open the decompiled C to check the summary. |
| **Can I pick the right callee to follow from the table alone?** | Yes — I fan out the function I wanted on the first try, not the third. |
| Do I keep returning to a saved view instead of restarting in Ghidra? | Yes, views become my working notes. |
| Does the canvas stay readable as I work? | Yes — after an hour of analysis I have ~10 deliberately-placed nodes, not 80 accidental ones. |

**Tier 2 — Engineering (measurable from DB + logs)**

| Metric | Target (v1) |
| --- | --- |
| Cache hit rate on summary requests after the first pass over a binary | ≥ 90% |
| Callstack paste → rendered graph, all summaries cached | < 2 s |
| Neighbour-table page (one row-cap page) API response, cached | < 300 ms |
| Fan-out click → node rendered on canvas | < 150 ms (no LLM call needed — row was pre-summarised) |
| Summaries requested per card placed (median, after D7 suppression) | ≤ 20 (median; worst case at default thresholds is ~33 — see §5.1) |
| Ingestion throughput | ≥ 5 functions/s (mock), ≥ 1 function/s (real Ghidra) |
| Summary generation failure rate | < 2% of calls |

---

## 2. User Personas & Key User Journeys

### 2.1 Personas

#### P1 — "Nadia", Vulnerability Researcher *(primary)*
- **Context:** Hunts memory-safety bugs in closed-source native binaries (Windows/Linux, C/C++).
- **Workflow today:** Ghidra + WinDbg/gdb + a text file of notes.
- **Needs:** Fast orientation from a crash callstack; identification of parsing / attacker-reachable code; understanding of data flow across function boundaries.
- **Success:** "I can tell within minutes which of the 12 frames in this stack touches untrusted input."
- **Frustration to remove:** Re-reading the same decompiled function three times because she lost context.

#### P2 — "Marcus", Malware Analyst *(primary)*
- **Context:** Triages samples under time pressure; writes reports for detection engineering.
- **Needs:** Rapid capability inventory (persistence, C2, injection, crypto); exportable, human-readable descriptions for reports.
- **Success:** "I can produce a capability summary of the sample's main flow in one pass."
- **Frustration to remove:** Manually paraphrasing decompiled functions into prose for the report.

#### P3 — "Sam", Reverse-Engineering Learner *(secondary)*
- **Context:** CTF player / student, limited experience reading decompiler output.
- **Needs:** Scaffolding — plain-language explanations that let them navigate before they can read pseudocode fluently.
- **Success:** "I understand the program's structure even where I can't yet read the C."

#### P4 — "Dana", RE Tooling Engineer *(operator persona)*
- **Context:** Runs the Ghidra ingestion script, manages the DB and LLM credentials.
- **Needs:** Reliable, resumable, idempotent ingestion; observability into what failed; cost control over LLM spend.
- **Success:** "One command, and the binary is queryable in the UI."

### 2.2 Key User Journeys

#### J1 — Ingest a binary (Dana)
1. Dana runs the ingestion script against an `.exe` and a Ghidra project.
2. Script (headless Ghidra) enumerates functions, extracts address, name, parameters, disassembly, decompiled C.
3. Script writes a `binaries` row and N `functions` + M `edges` rows into SQLite.
4. Script prints a summary: functions found, edges found, functions skipped and why.
5. Re-running the script on the same binary updates inherent fields but **must not** clobber LLM summaries or UI state.

#### J2 — Explore from an entry point (Nadia)
1. Nadia opens GraphRev, selects the binary from the binary picker, and creates a new **view** (or opens an existing one).
2. She opens `main` (searching by name, or pasting address `0x401a20`).
3. The canvas renders **exactly one card**: `main`. No neighbours are placed on the canvas.
4. The `main` card shows its own summary plus two tables:
   - **Calls (12)** — one row per callee: name + short summary, each with a `⤢` fan-out button.
   - **Called by (1)** — same shape, for callers.
5. Summaries for `main` *and* for every function listed in its tables auto-generate, so the tables become readable without any clicks. Rows show a shimmer until their summary lands.
6. She reads the 12 callee rows, recognises that `parse_config` and `init_network` are the interesting ones, and clicks `⤢` on those two rows only. They become canvas cards, each with their own tables. The other 10 callees stay as table rows — visible and summarised, but not cluttering the canvas.
7. She opens `parse_config`, whose **Calls (34)** table is scrollable at 16 visible rows; she scrolls, finds `read_key_value`, and fans that out.
8. She clicks a card to open the detail panel with the long summary, signature, her notes field, and (collapsed) decompiled C.
9. She renames `FUN_00401a20` to `parse_pe_header` (analyst name, Ghidra name preserved underneath), colors two nodes red ("attacker-reachable"), and jots a note on one. All of it persists to this view on reload.

**The key contrast with the old model:** landing on `main` used to place 13 nodes on the canvas. It now places 1 node that *describes* 13 functions. Nadia ends step 7 with 4 canvas nodes instead of ~40.

#### J3 — Paste a callstack (Nadia)
1. Nadia copies a list of return addresses (one per line) from her debugger.
2. She pastes it into the **Import Callstack** dialog.
3. GraphRev resolves each address to its containing function and reports resolved / unresolved lines.
4. Canvas renders the frames as a vertical chain in the pasted order — each line is assumed to **call the next** — with those edges highlighted as the **stack path**.
5. Summaries auto-generate for all resolved frames (queued, filling in as they complete).
6. Nadia expands sideways from the frame that looks like a parser.

#### J4 — Capability sweep (Marcus)
1. Marcus loads the binary and starts from `main` / the entry point in a view named "capability sweep".
2. He reads the callee table on `main` top-to-bottom — a summarised inventory of the program's top-level capabilities on a single card, without placing anything else on the canvas.
3. He fans out only the 3–4 rows that look like capability clusters (persistence, networking, crypto), then repeats the read-then-fan-out cycle on each.
4. He flags interesting nodes by color, renames the ones he has identified, and copies long summaries into his report.

*Note: the callee table is arguably a better fit for Marcus's job than the graph itself — a summarised call inventory is exactly the artifact he needs.*

#### J5 — Return to prior work (all)
1. Analyst reopens the **view** days later.
2. The previously visible nodes, their positions, colors, collapse state, analyst names, and notes are restored exactly — **and so is the camera**: same root, same pan, same zoom. She lands on the screen she left.
3. All summaries load from cache with no LLM cost.

#### J6 — Work several angles on one binary (Nadia)
1. Nadia keeps a "crash path" view and a separate "config parser" view over the same binary.
2. Layout, visibility, and colors are independent per view.
3. Summaries, analyst names, and notes are **shared** across views (they are properties of the function, not of the view).

---

## 3. Functional Requirements

Prioritized with **MoSCoW**: **M** = Must (v0/v1 ships without it = failure), **S** = Should (high value, first follow-up), **C** = Could (nice to have), **W** = Won't (explicitly deferred — see §5.2).

### Module A — Ingestion & Ghidra Integration

| ID | Req | Pri |
| --- | --- | --- |
| A1 | A standalone script populates SQLite with `binaries`, `functions` (address, name, parameters, assembly, decompiled C), and `edges` (caller → callee). | **M** |
| A2 | Ghidra access is abstracted behind an interface with a **mock implementation** that produces a deterministic synthetic binary (≈50–200 functions, realistic call graph, plausible names) for UI development. | **M** |
| A3 | Ingestion is idempotent: re-running updates inherent fields, preserves `summary_*` and all UI fields. | **M** |
| A4 | Ingestion reports counts and per-function failures without aborting the whole run. | **M** |
| A5 | Real Ghidra integration via REST/bridge or MCP, swappable via config. | **S** |
| A6 | Incremental ingestion (single function on demand, e.g. when an edge points to a function not yet in the DB). | **S** |
| A7 | Multiple binaries coexist in one DB; UI has a binary selector; mock adapter can generate ≥ 2 distinct synthetic binaries. | **M** |
| A7a | Ingestion computes `fan_in` per function and sets `is_utility` from it (D34a). The mock generator must produce a realistic fan-in distribution — including a few `memcpy`-class hubs — so demotion and suppression are exercised in M0. | **M** |
| A8 | Ingest imported/external/thunk functions as nodes with a distinct `kind` so library calls appear in the graph. | **S** |
| A9 | Symbol/PDB import to improve names. | **C** |
| A10 | Data-xref and string-reference edges. | **C** |

### Module B — Data Model & Persistence

**Decision (supersedes the schema in `idea.md`):** UI state is **not** stored on `functions`. It moves to a `view_nodes` join table so one binary can carry many independent views. Analyst name and notes stay on `functions` (they are facts about the function, not about a layout).

```
binaries    (id, name, version, created_at, last_view_id)
functions   (id, binary_id, address, name_ghidra, name_analyst, parameters,
             assembly, code_c,
             summary_short, summary_long, summary_status, summary_model,
             summary_generated_at, summary_input_hash,
             notes, notes_updated_at, kind)
edges       (id, binary_id, caller_id, callee_id, kind)
views       (id, binary_id, name, root_function_id,
             camera_x, camera_y, camera_zoom,
             created_at, updated_at)

-- functions also carries, computed at ingestion:
--   fan_in            INTEGER   number of distinct callers
--   is_utility        BOOLEAN   derived: fan_in > UTILITY_FANIN_THRESHOLD
--   utility_override  TEXT NULL 'always' | 'never' | NULL  (D36)
view_nodes  (id, view_id, function_id, visible, collapsed, color, pos_x, pos_y, pinned,
             origin_function_id, origin_kind, origin_implied)
```

**Enumerations (closed sets, M0):**

| Column | Values |
| --- | --- |
| `functions.kind` | `normal` (default) · `import` · `thunk` · `external` · `placeholder` — the last four are set only when the adapter supplies the information (A8, B17); the mock adapter must emit at least one of each so the UI is exercised. |
| `edges.kind` | `call` (only value in M0). Reserved for `data_xref` / `string_ref` (A10). |
| `functions.summary_status` | `none` · `pending` · `ready` · `error` · `stale` |
| `view_nodes.origin_kind` | `root` (placed by search/address entry) · `fanout` (D8, callee fan-out — new node grows *right*) · `fanin` (D8, caller fan-out — new node grows *left*) · `callstack` (D17) |
| `view_nodes.color` | one of a fixed palette of named tokens, not free-form hex (D16). |

`notes` is a plain `TEXT` column edited through a single textarea — no threading, no timestamped entries, no rich text (Q12). All timestamps are UTC, stored and transported as ISO-8601.

| ID | Req | Pri |
| --- | --- | --- |
| B1 | Schema as above: `binaries`, `functions`, `edges`, `views`, `view_nodes`. | **M** |
| B2 | `(binary_id, address)` is unique; address stored as an integer, rendered as hex in the UI. | **M** |
| B3 | Edges unique on `(caller_id, callee_id)`; self-edges (recursion) permitted. | **M** |
| B4 | UI state (`visible`, `collapsed`, `color`, `pos_x`, `pos_y`, `pinned`) persists server-side **per (view, function)**, not per function. | **M** |
| B4a | **Table-level UI state is ephemeral client state and is deliberately NOT persisted** (Q20): per-section collapse (callers/callees), the utility-group expanded flag, the D7 "Show anyway" choice, and per-table filter text and sort order. All of it resets to the D6/D7/D34 defaults on reload, on view switch, and on card re-place. This keeps `view_nodes` narrow; promoting any of it to persistence later is an additive column, not a redesign. | **M** |
| B4b | **Edge provenance:** a canvas node records how it got there — `origin_function_id` (the node it was fanned out from, `NULL` for a root or an unlinked frame), `origin_kind` (`root` / `fanout` / `fanin` / `callstack`), and `origin_implied` (true for a callstack chain link with no backing `edges` row, rendered dashed). `origin_kind` also fixes the derived edge's **orientation**: `fanout` (a fanned-out callee) points origin→node so the new node lays out to the *right*; `fanin` (a fanned-out caller) points node→origin so it lays out to the *left*. This is the *sole* source of canvas edges (D8b, Q21). | **M** |
| B5 | Summary metadata: `summary_status` (`none` / `pending` / `ready` / `error`), `summary_model`, `summary_generated_at`, `summary_input_hash`. | **M** |
| B5a | **Fan-in and utility classification** stored on `functions`: `fan_in` (distinct caller count, computed at ingestion), `is_utility` (derived), `utility_override` (nullable, analyst-set, survives re-ingestion like notes and names). | **M** |
| B6 | **Analyst name** (`name_analyst`, nullable) per function. When set it is the display name everywhere; `name_ghidra` is never overwritten and remains visible in the detail panel. | **M** |
| B7 | **Analyst notes** (`notes`, single plain-text field) per function; shared across all views of that binary; visually distinct from LLM output. One textarea, one string — not a log. | **M** |
| B8 | Views CRUD: create, rename, duplicate, delete. Deleting a view never deletes functions, summaries, names, or notes. | **M** |
| B9 | A default view is auto-created on first open of a binary so the user is never forced through a view-management step. | **M** |
| B10 | **View camera + root state:** a view persists its root function, pan offset, and zoom level, so reopening restores the exact framing the analyst left, not just node coordinates. | **M** |
| B10a | **`root_function_id` is the last-focused function** (Q22), not the origin of exploration: it is updated whenever the analyst selects a card, fans one out, or focuses one via `◎`. After a callstack import it is set to the **last frame in the imported chain**. Its only jobs are camera-restore context and the "you are here" hint; nothing in the graph model depends on it, and it may be `NULL` for an empty view. | **M** |
| B11 | Search matches both `name_ghidra` and `name_analyst`; notes are searchable too. | **S** |
| B12 | Migrations are versioned (Alembic or equivalent). | **S** |
| B13 | Analyst name and notes are fed into the summarization prompt as extra context. | **S** |
| B14 | Export/import of `name_analyst` (e.g. sync back to a Ghidra project). Not needed now — renames stay internal to GraphRev. | **W** (v1) |
| B15 | Multi-user / auth-scoped views. Views are the seam that makes this cheap later, but no user table in v1. | **W** (v1) |
| B16 | **Last-used view per binary** persists (`binaries.last_view_id`) so switching binaries restores that binary's working context (§4.3). | **M** |
| B17 | **Placeholder functions** (Q24): when ingestion finds an edge whose target is not in the binary — a call into a DLL when only the EXE was analysed, or into an unanalysed module — it creates a real `functions` row with `kind = 'placeholder'`, the known address, the best available name, and `assembly`/`code_c` `NULL`. Edge FK integrity is therefore never violated, and the call is visible in the table. A later full ingestion of that module (or A6) upgrades the row in place, preserving its id, summary, name, and notes. | **M** |
| B18 | **Concurrency policy: none** (Q27). Single user, single tab assumed; all writes are last-write-wins with no version column, no ETag, no optimistic-concurrency check. Recorded as a deliberate simplification, not an oversight. | **M** |

### Module C — Summarization (LLM Agent)

**Ownership boundary:** the real LLM call, model choice, and **prompt engineering are owned by the user, outside this PRD.** GraphRev's responsibility is the *contract* around it: a swappable adapter, a cache, a queue, status tracking, and error surfacing. The adapter interface is therefore a Must; the prompt's content is not specified here.

Adapter contract (conceptual):

```
summarize(function: {address, name, parameters, code_c, assembly,
                     analyst_name?, notes?, callee_summaries?[]})
    -> {summary_short: str, summary_long: str, model: str}
    | raises SummarizationError
```

| ID | Req | Pri |
| --- | --- | --- |
| C1 | Agent access is abstracted behind the adapter interface above, with a **mock implementation** returning deterministic, latency-simulating fake summaries (random 1–8 s delay, ~5% synthetic failure rate to exercise error states). | **M** |
| C2 | **Auto-summarize on load:** when a function needs a summary for display — as a canvas card **or as a row in a visible callee/caller table** — generation starts automatically. No user click. There is no "Analyze" button in the happy path. | **M** |
| C2a | **Table rows are the dominant demand driver.** Placing one card requires summaries for the card *plus* all rows in its tables. Cost is bounded by: the D7 hub suppression (no summaries for a suppressed 291-caller list), row virtualisation (D6 — prioritise rendered rows only, queue the rest lazily on scroll), and the fact that fan-out adds no new summaries (the row was already summarised). `TABLE_ROW_CAP` therefore doubles as a cost control. | **M** |
| C2b | **Collapsed groups are not rendered, so they are not queued.** Utility rows (D34) *do* get summaries — they are not excluded — but as a collapsed group their generation is deferred until the group is expanded. Same rule as off-screen scroll rows; no special case. | **M** |
| C2c | **The client drives demand, one request per function** (Q23). Fetching a neighbour table does **not** enqueue anything server-side; the client explicitly requests a summary for each row it actually renders, keyed by function id. Requests are per-function, never per-table and never batched-by-card, so virtualisation and lazy-on-expand are real cost controls rather than rendering niceties, and de-duplication (§5.1) has a single natural key. | **M** |
| C3 | Cache-first: cached summaries are never regenerated implicitly. | **M** |
| C4 | Two summaries per function: `summary_short` = **1–3 lines** (card display **and table rows** — it must read well in a narrow row, not just a card), `summary_long` = **~5 lines** (detail panel). Content/format is prompt-owned, not specified here. | **M** |
| C5 | Concurrency control: max N in-flight generations (default assumption: 4); bounded FIFO queue. Priority order: **selected card > its visible table rows > other visible cards > off-screen rows**. | **M** |
| C5a | **Generation is a background worker, decoupled from the request that asked for it.** A summary request writes `summary_status = 'pending'`, enqueues, and returns immediately — it never holds the HTTP connection open for the 2–15 s the LLM takes (AS5). Work therefore survives the requesting client navigating away, closing the card, or closing the tab; the queue is owned by the server, not by a page. | **M** |
| C5b | **Restart recovery:** on server start, any function left at `summary_status = 'pending'` from a previous process is reconciled — reset to `none` (and re-requested by the client when next rendered) or re-enqueued. A crash must never leave a function permanently stuck showing "Analyzing…" with no worker behind it. | **M** |
| C6 | Failures surface as an error state on the card with a **Retry** action; failures are not cached as valid summaries. | **M** |
| C7 | Explicit **Regenerate** action per node (needed precisely because C2 removes the manual trigger). | **M** |
| C8 | Cancellation: hiding a node, collapsing a table section, or closing the view cancels its still-queued generation, so auto-summarize cannot run away. Cancellation applies only to **queued-but-unstarted** work; in-flight generations always run to completion and are cached. Because summaries are function-scoped and shared, a cancel request drops the item only if **no other visible surface still demands it**. | **M** |
| C9 | Prompt context enrichment: pass callee names/short-summaries, analyst name, and notes to the adapter so summaries improve with graph depth. | **S** |
| C10 | Stale detection: if `summary_input_hash` no longer matches the decompiled C, mark the summary **stale**. | **S** |
| C11 | Cost/usage tracking (tokens, calls, estimated spend) surfaced in the UI. | **S** |
| C12 | Batch/background pre-summarization of an entire binary. | **C** |
| C13 | LLM-*proposed* analyst names, which the user accepts or rejects into `name_analyst`. | **C** |
| C14 | Streaming token-by-token summary rendering. | **C** |
| C15 | Multi-agent iterative refinement across the whole graph. | **W** (v1) |

### Module D — Graph Canvas & Navigation

**Navigation model (v0.4 — supersedes automatic 1-hop expansion):** a card is a self-contained view of its own neighbourhood. Neighbours are listed *in tables on the card*, not placed on the canvas. The canvas only ever contains functions the analyst explicitly fanned out. See §4.2 for the card anatomy and the threshold rationale.

| ID | Req | Pri |
| --- | --- | --- |
| D1 | Render function cards as nodes and calls as directed edges (React Flow). | **M** |
| D2 | Entry: search by function name (substring, case-insensitive) or jump by address. | **M** |
| D3 | **Root-only load:** selecting a root places exactly **one** card on the canvas. Neighbours appear in that card's tables, not as nodes. | **M** |
| D4 | **Callee table ("Calls"):** every callee as a row of *name + short summary*, with a per-row fan-out control. Header shows the total count. | **M** |
| D5 | **Caller table ("Called by"):** identical structure for callers, subject to the D7 hub rule. | **M** |
| D6 | **Table height cap:** show at most `TABLE_ROW_CAP` rows (**default 16**); beyond that the table body scrolls internally. Cards for bigger functions are legitimately taller — that is useful signal — but bounded. | **M** |
| D7 | **Caller-table hub suppression:** if a function has more than `CALLER_SUPPRESS_THRESHOLD` callers (**default 32**), collapse the caller table by default to a single line ("Called by 291 functions — show anyway"), because a `memcpy`-style caller list is noise. The callee table is **never** suppressed this way (a function's own callees are always meaningful, however many). | **M** |
| D7a | Both thresholds are **configuration values, not hard-coded constants** (F1a), and are expected to be re-tuned once real binaries are loaded. | **M** |
| D8 | **Per-row fan-out:** clicking a row's fan-out control promotes that one function to a canvas node, with its own tables, and draws the connecting edge. Direction determines which side it lands on: fanning out a **callee** row places the new card to the **right** (`origin_kind = fanout`), a **caller** row to the **left** (`origin_kind = fanin`), so the graph grows both ways from any card. **No automatic expansion, ever.** Fan-out is click-only — no drag-and-drop. | **M** |
| D8b | **Canvas edges come from fan-out provenance only** (Q21): an edge is drawn if and only if a visible node records the other as its `origin_function_id` (B4b), or the pair is consecutive in an imported callstack chain. Its **orientation** follows `origin_kind` (B4b): `fanin` reverses the edge relative to `fanout`, which is what places a fanned-out caller to the left. Edges are **not** derived from the full `edges` table between visible nodes — two nodes placed independently show no connector even if a call relationship exists. Deliberately simple: the canvas shows the analyst's path of reasoning, and the tables remain the authoritative record of actual call relationships. | **M** |
| D8a | A newly fanned-out card opens in the **default state** (tables expanded per the D6/D7 rules); it does **not** inherit the collapse or filter state of the card it came from. Predictability beats cleverness here. | **M** |
| D9 | Fan-out state is reflected in the row: an already-on-canvas row is marked as such, and its control becomes "focus" (pan to the existing node) rather than a duplicate add. | **M** |
| D10 | Rows are clickable independently of fan-out: clicking a row body opens that function in the **detail panel** (read without committing it to the canvas). | **M** |
| D11 | Automatic layout via ELK.js (layered, call direction top→bottom or left→right), preserving manual positions once a node has been moved. Must accommodate variable-height cards. | **M** |
| D12 | Pan, zoom, fit-to-view, minimap. Pan/zoom are **persisted to the view** (debounced) so reopening restores the exact framing (B10). | **M** |
| D13 | Hide / remove a node from the canvas (`visible = false`) without deleting data. Its rows revert to un-fanned-out state in other cards' tables. | **M** |
| D14 | Collapse a node to a compact chip (name only, tables hidden). | **M** |
| D15 | Manual drag repositioning, persisted per view; a moved node becomes `pinned` and is exempt from auto-layout. | **M** |
| D16 | Node color assignment from a small palette. | **M** |
| D17 | **Callstack paste:** input is a newline-separated list of addresses, ordered so that **each line calls the next**. Each address resolves to its containing function; the chain renders in order with those edges highlighted as the stack path. Unresolved lines are reported. This is the one flow that legitimately places many nodes at once — the user asked for that chain explicitly. | **M** |
| D18 | Detail side panel: display name, Ghidra name, address, signature, long summary, **analyst notes editor**, and collapsible raw assembly / decompiled C. | **M** |
| D19 | **Rename affordance:** inline rename on the card and in the detail panel, writing `name_analyst`; a subtle marker shows the name is analyst-supplied, with the Ghidra name on hover and a **Reset to Ghidra name** action. | **M** |
| D20 | **Notes affordance:** a plain textarea in the detail panel with debounced autosave; cards with notes show a note indicator (📝) so annotated functions are findable at a glance. | **M** |
| D21 | View management UI: view switcher, create / rename / duplicate / delete view. | **M** |
| D21a | **Minimal sidebar:** an "on canvas" node list (jump-to, notes/rename indicators) plus the glyph legend. **No browsable function tree** — card tables plus toolbar search cover navigation. Collapsible, and a candidate for removal if unused. | **M** |
| D22 | **In-table filter:** for tables over the row cap, a filter box narrowing rows by name/summary text, so a 200-callee table stays usable. | **S** |
| D23 | **Table sorting:** by name, address, or callee-count/fan-in, so the interesting rows can be surfaced without scrolling. | **S** |
| D24 | **Fan out all visible/filtered rows** as one deliberate action, with a confirmation naming the node and LLM cost. | **S** |
| D25 | Highlight all paths between two selected nodes. | **S** |
| D26 | Filter/search within the visible graph (highlight matching cards). | **S** |
| D27 | Row-level indicators: recursion (`↻`), already-visited, has-notes, is-renamed. (The utility glyph `▫` is part of D34 and is a Must.) | **S** |
| D28 | Group/cluster nodes into user-named regions (e.g. "parser", "crypto"). | **C** |
| D29 | Export canvas as PNG/SVG, and export summaries + notes as Markdown. | **C** |
| D30 | Per-row **call-site count** badge (`×3`). Not wanted — one row per unique callee is sufficient. | **W** |
| D31 | Drag-and-drop of table rows onto the canvas as an alternative to the fan-out click. | **W** |
| D32 | Diff two binary versions on the graph. | **W** (v1) |
| D33 | Real-time collaborative editing of a view. | **W** |
| **D34** | **Utility demotion in callee tables:** rows whose function is classified `utility` sort to the **bottom** of the callee table, grouped under a collapsible `▸ utility calls (N)` sub-header, **collapsed by default**. Nothing is hidden or removed — the count is always visible and one click expands the group. | **M** |
| D34a | The classifier is a **single isolated predicate** (`is_utility(function)`), swappable without UI changes. v0 implementation: `fan_in > UTILITY_FANIN_THRESHOLD` (default 50). | **M** |
| D35 | Utility rows are **fully functional** when expanded: same summary, same fan-out control, same detail-panel click. Demotion affects ordering and default visibility only — never capability. | **M** |
| D35a | **Placeholder rows and cards** (B17): a `placeholder` function renders as a normal row and is fully fannable, with a `≡` glyph and a "not analyzed — outside the ingested module" note in place of code. Its detail panel states which module the address falls outside of, if known. It is summarisable from name alone (flagged low confidence, §4.3), never a dead row. | **M** |
| D36 | **Manual override**, persisted per function: "always treat as utility" / "never treat as utility", so a misclassified dispatcher can be corrected once and stay corrected. | **S** |
| D37 | Caller tables apply the same grouping when shown via "Show anyway", so a hub's own caller list is also ordered usefully. | **C** |

### Module E — Backend API

| ID | Req | Pri |
| --- | --- | --- |
| E1 | FastAPI service: list binaries; delete a binary; views CRUD; search functions (paginated); get function by id/address; get a function's neighbour tables; patch view-node state; patch view state; patch analyst name/notes; request/cancel/regenerate summary; read queue state; suggested entry points; resolve an address list; read config constants. | **M** |
| E1a | **Search is paginated and indexed** (AS10): substring match over `name_ghidra` and `name_analyst` with an explicit limit and offset; never an unbounded result set. | **M** |
| E1b | **Suggested-entry-points endpoint:** up to 5 candidates for the empty-canvas state — known entry names (`main`, `WinMain`, `DllMain`, the binary entry point) plus highest-fan-in functions (§4.3). | **M** |
| E1c | **Queue-state endpoint** backing the `◌ 3 of 12` chip: in-flight and queued function ids with counts, plus a cancel-pending action (C8). | **M** |
| E1d | **Config endpoint** exposing the F1a constants to the frontend as one payload, so no threshold is duplicated in client code. | **M** |
| E2 | **Neighbour-table endpoint:** for one function **within a given view** (`view_id` is required, since `on_canvas` is a view fact), return its callees and callers as rows of `{id, address, display_name, summary_short, summary_status, kind, on_canvas, is_utility, utility_source, fan_in}` plus total counts, **paginated** (default page size = `TABLE_ROW_CAP`, so one page fills one table) and independently sortable/filterable. Fetching this endpoint has **no side effects** — it never enqueues summaries (C2c). This replaces the old "fetch the whole 1-hop subgraph" call. | **M** |
| E2a | Response includes `callers_suppressed: true` when the caller count exceeds the D7 threshold, so the client renders the collapsed state without fetching 291 rows. | **M** |
| E2b | Each row carries `fan_in` plus the **effective** utility classification: `is_utility` already has `utility_override` applied (Q25), and `utility_source` (`computed` / `analyst`) lets the UI mark analyst-set rows (§4.3). Rows are returned **already ordered** with utility rows last, so the client neither re-derives the grouping nor re-applies the override. Utility rows may be requested as a separate page to keep the primary page dense. | **M** |
| E2c | Endpoint to set/clear `utility_override` for a function (D36). | **S** |
| E3 | Batch view-node state patch (avoid one request per drag frame; debounce client-side). | **M** |
| E3a | Patch view-level state (root function, camera x/y/zoom), debounced separately from node state. | **M** |
| E4 | Structured errors with machine-readable codes. | **M** |
| E5 | **Async summary flow is mandatory** (C2 makes many summaries in flight the normal case): requesting a summary returns `pending` **immediately**, never blocking on generation (C5a); the client learns of completion over a **single SSE stream** carrying summary-status and queue-state events. **SSE only** — no WebSocket, no polling fallback (Q26); on stream loss the client reconnects and reconciles from `summary_status`, which is authoritative (§5.1). | **M** |
| E5a | **The SSE completion event carries the result**, not just a notification: `{function_id, summary_status, summary_short, summary_model, generated_at}` (and `error_code` on failure), so the client patches the card and *every* table row showing that function in place — no refetch, no card reload, no layout reflow. One event updates all surfaces displaying that function, since summaries are function-scoped. | **M** |
| E5b | **Queue-state events** are emitted on the same stream (enqueued / started / finished / cancelled counts) so the `◌ 3 of 12` chip is push-driven rather than polled. | **M** |
| E6 | Address-list resolution endpoint: given ordered addresses, return the containing function per address plus unresolved entries, and for each consecutive pair whether a backing `edges` row exists (so the client knows which chain links to render dashed — B4b `origin_implied`). | **M** |
| E7 | OpenAPI docs auto-published. | **S** |
| E8 | Rate limiting and auth. | **W** (v1, single-user local tool) |

### Module F — Operations & Configuration

| ID | Req | Pri |
| --- | --- | --- |
| F1 | Config via env/file: DB path, Ghidra adapter (mock/real), LLM adapter (mock/real), model name, concurrency limits. | **M** |
| F1a | **UI tuning constants are configurable**, surfaced to the frontend from one place: `TABLE_ROW_CAP` (default 16), `CALLER_SUPPRESS_THRESHOLD` (default 32), `UTILITY_FANIN_THRESHOLD` (default 50), `FAN_OUT_ALL_HARD_CAP` (default 50), `NODE_COUNT_SOFT_WARNING` (default 150). No magic numbers in components. | **M** |
| F1b | Changing `UTILITY_FANIN_THRESHOLD` must be cheap: either recompute `is_utility` on startup, or evaluate it from stored `fan_in` at query time. A threshold change must never require re-ingestion. | **M** |
| F2 | Structured logging of ingestion and LLM calls. | **M** |
| F3 | Single-command local dev startup (backend + frontend). | **M** |
| F4 | Health endpoint reporting DB and adapter status. | **S** |
| F5 | Containerized deployment. | **C** |

---

## 4. UI/UX Wireframe Concepts & State Requirements

### 4.1 Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ GraphRev  [ acme.exe v1.2 ▾ ] [ View: crash path ▾ ] [ 🔍 name / 0xADDR   ]  │
│                              [ Paste Callstack ] [ Fit ] [ ◌ 3 of 12 ] [ ⚙ ] │
├───────────────┬──────────────────────────────────────────┬───────────────────┤
│  SIDEBAR      │                CANVAS                    │  DETAIL PANEL     │
│  (minimal)    │                                          │  (opens on select)│
│               │   ┌───────────────────────────┐          │ parse_config    ✎ │
│ ON CANVAS (2) │   │ ● main            ✎📝 ⋯ ✕ │          │ ↳ FUN_00401a20    │
│ ───────────── │   │   0x00401000 · 2 params   │          │   0x00401a20      │
│ • main        │   ├───────────────────────────┤          │ ───────────────── │
│ • parse_con 📝│   │ Program entry; parses     │          │ int FUN_00401a20( │
│               │   │ argv and dispatches.      │          │   char* buf,      │
│               │   ├───────────────────────────┤          │   size_t len)     │
│               │   │ ▸ CALLED BY (1)           │          │ ───────────────── │
│               │   ├───────────────────────────┤          │ ✨ SUMMARY        │
│               │   │ ▾ CALLS (12)              │          │ Reads the DOS…    │
│               │   │ ◎ parse_config  Parses…   │          │ (~5 lines)        │
│ LEGEND        │   │ ⤢ init_network  Sets up…  │          │ ───────────────── │
│ ───────────── │   │ ⤢ setup_logging Configu…  │          │ 📝 MY NOTES       │
│ ◌ loading     │   │ ⤢ run_loop      Main ev…  │          │ ┌───────────────┐ │
│ ! error       │   │ ⤢ cleanup       Frees a…  │          │ │ len is attacker│ │
│ 📝 has notes  │   │ … 7 more (scroll)         │          │ │ controlled!    │ │
│ ✎ renamed     │   └─────────────┬─────────────┘          │ └───────────────┘ │
│ ⤢ fan out     │                 │ (fanned out)           │ ▸ Parameters (2)  │
│ ◎ on canvas   │   ┌─────────────▼─────────────┐          │ ▸ Decompiled C    │
│ ▫ utility     │   │ ● parse_config    ✎📝 ⋯ ✕ │          │ ▸ Assembly        │
│               │   │   … own tables …          │          │ [Regenerate] [🎨] │
└───────────────┴───┴───────────────────────────┴──────────┴───────────────────┘
```

The toolbar carries three pickers in a deliberate hierarchy: **binary → view → search**. The `◌ 3 of 12` chip is the auto-summarize queue indicator — with C2 it is a permanent, load-bearing piece of UI, not an edge case.

**The sidebar is deliberately minimal** (D21a): an "on canvas" list for orientation and jump-to, plus the glyph legend. It is *not* a second navigation surface — the card tables have made a browsable function tree redundant, and entry into the graph happens through toolbar search. Candidate for collapsing entirely if it proves unused.

Note the canvas holds only **two** nodes here, yet 13 functions are visible and summarised. That ratio is the point of the design.

### 4.2 Function Card Anatomy

The card is the primary navigation surface. It has four zones: **header**, **own summary**, **callers table**, **callees table**.

```
┌───────────────────────────────────────────────────────────────┐
│ ●  parse_config                        ✎ 📝      ⋯   ✕       │
│    0x00401a20 · 2 params                                      │
├───────────────────────────────────────────────────────────────┤
│ Parses the on-disk configuration file into the global config   │
│ struct, validating each key against a whitelist.               │
├───────────────────────────────────────────────────────────────┤
│ ▾ CALLED BY (3)                                               │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │ ⤢  main              Program entry; parses argv and…      │ │
│ │ ⤢  reload_config     Re-reads config on SIGHUP.           │ │
│ │ ◎  init_service      Bootstraps the service worker…       │ │ ← ◎ = already on canvas
│ └───────────────────────────────────────────────────────────┘ │
├───────────────────────────────────────────────────────────────┤
│ ▾ CALLS (34)                                    [filter…] ⇅   │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │ ⤢  open_file         Opens a path with mode flags…        │▲│
│ │ ⤢  read_line         Reads one newline-delimited record.  │║│
│ │ ⤢  trim_whitespace   Strips leading/trailing spaces.      │║│
│ │ ⤢  lookup_key    ↻   Recursive whitelist lookup.          │║│
│ │ ⤢  parse_int         Converts decimal text to int32.      │║│
│ │ ⤢  set_config_val    Writes a validated value into…       │║│
│ │ ⤢  validate_key      Checks a key against the whitelist.  │║│ │
│ │ ⤢  free_buffer   ◌   Analyzing…                           │║│ ← meaningful rows
│ │ ─────────────────────────────────────────────── │║│    first
│ │ ▸ ▫ utility calls (7)                                     │▼│ ← collapsed, at
│ └───────────────────────────────────────────────────┘ │    the bottom
│                                    showing 16 of 34  [Fan all]│
└─────────────────────────────────────────────────────────┘
```

Utility group expanded (D34) — rows are fully functional, summaries and all (D35):

```
│ │ ▾ ▫ utility calls (7)                                     │ │
│ │   ⤢  memcpy      ▫   Copies n bytes between buffers.       │ │
│ │   ⤢  free        ▫   Releases a heap allocation.           │ │
│ │   ⤢  strlen      ▫   Returns the length of a C string.     │ │
```

Hub case — caller table suppressed (D7):

```
├───────────────────────────────────────────────────────────────┤
│ ▸ CALLED BY (291)  — too many to list · [ Show anyway ]        │
├───────────────────────────────────────────────────────────────┤
```

Collapsed variant (D14):

```
┌───────────────────────────┐
│ ● parse_config ✎📝 ⌄      │
└───────────────────────────┘
```

**Row anatomy:** `[fan-out control] [name] [status/kind glyphs] [short summary, single-line clamp]`

| Control / glyph | Meaning |
| --- | --- |
| `⤢` | Fan out — promote this function to a canvas node (D8) |
| `◎` | Already on canvas — click to pan/focus it instead (D9) |
| `◌` | Summary generating |
| `↻` | Recursive / part of a cycle |
| `▫` | Utility (high fan-in) — sorted into the collapsed utility group (D34) |
| `≡` | Placeholder — outside the ingested module, not analyzed (D35a) |
| `📝` `✎` | Has notes / renamed by analyst |

M0 ships `⤲`, `◎`, `◌`, `▫`, `≡`, and the error `!`. The `↻`, `📝`, and `✎` **row-level** glyphs arrive with D27 (**Should**) — except `↻` on the self-recursion row, which D8/§5.1 require in M0 to explain why fan-out is disabled there. `📝` and `✎` on the **card header** are M0 (D19, D20).

Card menu (`⋯`): Collapse · **Rename** · **Edit notes** · Set color · Regenerate summary · Copy address · Hide.

**Design notes**
- Clicking a **row body** opens that function in the detail panel *without* adding it to the canvas (D10) — cheap reconnaissance before committing.
- The card allocates 3 lines to its own `summary_short`, but table rows clamp to **one line** — this is why `summary_short` must front-load meaning (C4).
- Table sections are individually collapsible (`▾`/`▸`). This state — along with the utility-group toggle, "Show anyway", filter text, and sort order — is **ephemeral client state, not persisted** (B4a); it resets to defaults on reload and on view switch.
- Card width is fixed; only height varies. Taller cards for busier functions are intentional signal.
- Both tables have a soft empty state: "No callers found (possible entry point or indirect-only)" / "No callees (leaf function)".

### 4.3 State Matrix

| Surface | State | Behavior / Visual |
| --- | --- | --- |
| **App** | Initial / no binary | Empty state: "No binaries ingested. Run the ingestion script." with a copyable command and doc link. |
| **App** | Backend unreachable | Blocking banner + retry; canvas frozen, no data loss. |
| **App** | Multiple binaries | Binary picker lists name + version + function count; switching binaries switches to that binary's last-used view (`binaries.last_view_id`, B16), or its default view if none. |
| **App** | Deleting a binary | Typed-confirmation dialog naming the binary and the count of notes and analyst names about to be destroyed; cascades to functions, edges, views, and view-nodes (§5.1). |
| **View** | No view exists for binary | A default view named "Main" is created silently (B9); the user never sees a blocking "create a view" step. |
| **View** | Switching views | Canvas cross-fades and restores that view's saved camera and root; pending summaries continue (they are function-scoped, not view-scoped). |
| **View** | Reopened after days | Node positions, colors, visibility, pan/zoom, and last-focused function are restored (B10) — the analyst lands on the same screen they left. Table collapse, filters, and "Show anyway" reset to defaults (B4a). |
| **App** | SSE stream drops | Reconnect with backoff; on reconnect, re-read `summary_status` for visible functions and queue state rather than trusting client memory. A quiet "reconnecting…" affordance, not a blocking banner. |
| **View** | Saved camera now invalid (all its nodes hidden or deleted) | Fall back to fit-to-view rather than restoring a camera pointed at empty space. |
| **View** | Deleting a view | Confirm dialog stating explicitly that summaries, names, and notes are kept and only the layout is discarded. |
| **Canvas** | Empty (binary loaded, no root chosen) | Centered prompt: search box, "Paste a callstack", and up to 5 suggested entry points (`main`, `WinMain`, `DllMain`, entry, highest fan-in). |
| **Canvas** | Loading a card | Skeleton card with skeleton table rows at the correct row count (count is known before summaries are). |
| **Canvas** | Layout re-flowing | Animated transition ≤ 400 ms; pinned (manually moved) nodes do not move. Must handle cards changing height as tables expand/collapse. |
| **Canvas** | Fan-out in progress | The originating row shows a spinner; the new card animates in from that row's position so the causal link is legible. |
| **Canvas** | Newly fanned-out card | Opens in the **default** table state regardless of the originating card's collapse/filter state (D8a) — predictable, not inherited. |
| **Canvas** | Two nodes placed independently that do call each other | **No connector is drawn** (D8b) — canvas edges reflect fan-out provenance, not the full edge set. Each card's tables still show the other with `◎`, which is where the relationship is legible. |
| **Canvas** | Node hidden whose fan-out children remain visible | Children keep their `origin_function_id` but their edge is not rendered while the parent is hidden; re-showing the parent restores the connector. Children are never cascaded away. |
| **Table** | Loading rows | Row names and addresses render immediately (cheap from DB); summary cells shimmer independently until each lands. The table is navigable before any summary arrives. |
| **Table** | Rows ≤ cap | Renders at natural height, no scrollbar. |
| **Table** | Rows > cap | Body scrolls internally at cap height; footer shows "showing 16 of N"; filter and sort controls appear (D22/D23). |
| **Table** | Callers over suppression threshold (D7) | Section collapsed to one line: "Called by 291 functions — too many to list · **Show anyway**". No row summaries are requested while suppressed. |
| **Table** | Suppressed, user clicked "Show anyway" | Expands to the standard scrollable capped table. The choice is **session-only** and resets on reload (B4a). |
| **Table** | Contains utility callees (D34) | Meaningful rows first; utility rows collected at the bottom under `▸ ▫ utility calls (7)`, collapsed by default. The count is always visible so nothing feels hidden. |
| **Table** | Utility group expanded | Rows render normally with `▫` glyphs; their summaries begin generating on expand (C2b) and shimmer until they land. Fan-out and row-click work identically to any other row. |
| **Table** | All callees are utility | Primary list shows the empty-ish state "all 7 calls are utility functions" with the group present — never a blank table above a collapsed group. |
| **Table** | Utility row manually overridden (D36) | Moves into/out of the group immediately; a small marker distinguishes analyst-set classification from computed. |
| **Table** | Empty — no callees | "No callees (leaf function)". |
| **Table** | Empty — no callers | "No callers found — possible entry point, or reached only via indirect calls." |
| **Table** | Row's function already on canvas | `◎` marker, row de-emphasised, control becomes **focus** (pan to node) rather than fan-out (D9). |
| **Table** | Row is the card's own function (self-recursion) | `↻` glyph, fan-out disabled with tooltip "recursive call to itself". |
| **Table** | Row summary failed | Summary cell shows "— analysis failed", inline retry; the row stays usable for fan-out regardless. |
| **Table** | Row is a placeholder (B17, D35a) | `≡` glyph; summary generated from the name alone and marked low-confidence; fan-out permitted. Row copy on hover: "outside the ingested module — no code available". |
| **Table** | Filter matches nothing | "No rows match 'foo' — clear filter". |
| **Table** | Fan-out-all confirmation (D24) | "Fan out 34 functions? This adds 34 cards to the canvas." Disabled or extra-guarded above `FAN_OUT_ALL_HARD_CAP`. |
| **Card** | No summary yet | Neutral/grey card, hollow dot — transient only, since C2 immediately moves it to pending. No **Analyze** button exists. |
| **Card** | Summary pending | Shimmer placeholder lines, pulsing dot, "Analyzing…"; card remains draggable, renameable, and expandable. |
| **Card** | Summary queued (not started) | Dimmed dot + "Queued" label; **Cancel** available via the queue popover. |
| **Card** | Summary ready | Full-contrast card, filled dot, 1–3 line short summary rendered. |
| **Card** | Summary stale (C10) | Filled dot + amber ring; tooltip "Code changed since summary"; **Regenerate** emphasized. |
| **Card** | Summary error | Red left border, `!` dot, "Analysis failed — <reason>", **Retry** button. Name/address/notes remain visible and usable. |
| **Card** | No decompiled C available | Detail panel shows "Decompilation unavailable (thunk/imported)"; the adapter still receives the request and may return a name-based summary, flagged as low confidence. |
| **Card** | Renamed by analyst | Title shows `name_analyst` with a `✎` marker; hover reveals the Ghidra name; detail panel shows both. |
| **Card** | Has notes | `📝` indicator in the header; also flagged in the sidebar list. |
| **Card** | All neighbours fanned out | Every row shows `◎`; no special card-level state needed — the tables remain the record of the neighbourhood. |
| **Card** | Recursive (self-edge) | Self-loop edge badge "↻ recursive"; the self-row in its own callee table is marked and non-fannable. |
| **Card** | Very tall (both tables at the cap) | Capped by construction: header + summary + 2 × `TABLE_ROW_CAP` rows. ~700 px at the default cap; lower the cap if this proves unwieldy. |
| **Detail panel** | Nothing selected | Hidden or collapsed to a thin rail. |
| **Detail panel** | Long summary pending | Skeleton text; short summary shown if already available. |
| **Detail panel** | Notes empty | Placeholder "Add your notes…" — a single click focuses the textarea. |
| **Detail panel** | Notes saving / saved | Debounced autosave with a quiet "Saved" affordance; never a modal or explicit Save button. |
| **Detail panel** | Notes long | Textarea scrolls / grows to a capped height; no pagination, no separate editor window. |
| **Detail panel** | Selection changes with unsaved keystrokes | Flush the pending save before switching functions — notes must never be silently lost. |
| **Detail panel** | Rename conflict | If `name_analyst` duplicates another function's name, allow it but warn inline (names are labels, not identifiers). |
| **Callstack dialog** | Empty | Textarea with hint: "One address per line, outermost first — each line is assumed to call the next." Example block shown. |
| **Callstack dialog** | Partial resolution | Per-line list: ✓ resolved (`0x401a20 → parse_pe_header`), ⚠ unresolved with reason (`no function contains this address`, `not a valid address`). Button: **Import resolved (7 of 10)**. |
| **Callstack dialog** | Zero resolution | Error state: "No addresses matched this binary. Is the right binary selected?" |
| **Callstack dialog** | Order ambiguity | A **Reverse order** toggle with a live preview of the resulting chain, since debuggers disagree on stack direction. |
| **Search** | No results | "No function matches 'foo'. Try an address (0x…) or a partial name." |
| **Queue** | Backlogged | Toolbar chip "◌ 3 of 12" with a popover listing in-flight and queued functions, plus **Cancel pending**. |
| **Queue** | Idle | Chip collapses to a checkmark or hides entirely. |

### 4.4 Interaction & Accessibility Principles

- **Semantics first:** no card ever shows assembly or C by default; raw code is one deliberate click away.
- **The user places every node.** Nothing reaches the canvas without an explicit fan-out click (the pasted callstack being the one requested exception). Growth is always attributable to a user action.
- **Read before you commit.** The tables let the analyst evaluate a neighbourhood — names *and* summaries — without paying canvas clutter for it. Row-click opens the detail panel; only `⤢` adds a node.
- **No layout surprises:** the user's manual positions are sacred. Auto-layout applies only to newly added, unpinned nodes.
- **Non-blocking async:** a pending summary never blocks navigation, expansion, renaming, or note-taking.
- **Render what you have, immediately.** Ground truth from the DB — names, addresses, parameters, row counts, table structure — is cheap and must paint at once; LLM summaries are the *only* thing allowed to arrive late, and they fill into place without moving anything around. A card or table is never withheld waiting on a summary, and a late-arriving summary must not reflow the layout.
- **Background work is always visible.** In-flight generation is surfaced at three scales simultaneously: the global queue chip (`◌ 3 of 12`), the per-card pulsing dot with "Analyzing…", and the per-row `◌` glyph with a shimmering summary cell. The analyst can always tell that the system is working and roughly how much is left.
- **Three-tier truthfulness:** the UI visually separates (1) **ground truth** from Ghidra — address, parameters, code — in monospace; (2) **LLM output** — marked `✨`, distinct type treatment; (3) **analyst input** — names marked `✎`, notes marked `📝` in a clearly authored style. The analyst must never wonder who wrote a given line.
- **Analyst input outranks machine output:** where an analyst name exists, it replaces the Ghidra name everywhere, and it is fed back into the prompt (B13).
- **Keyboard:** `/` focus search, `Enter` open detail, `↑`/`↓` move between table rows, `→` fan out the focused row, `N` edit notes, `F2` rename, `Esc` close panel. Table rows must be keyboard-navigable — they are the primary navigation control, so they cannot be mouse-only.
- Colors always paired with a shape/icon cue (colorblind-safe); target WCAG AA contrast on card text.

---

## 5. Edge Cases & Scope Boundaries

### 5.1 Edge Cases to Handle

**Graph topology**
- Recursive functions (self-edges) and mutual recursion → render self-loop; the function's own row in its callee table is marked `↻` and fan-out is disabled (it is already the card).
- Mutual recursion `A → B → A` → fanning out `B` from `A` shows `A` in `B`'s caller table marked `◎`; no loop, no duplicate node.
- Cycles in the call graph → ELK layered layout must handle back-edges without exploding.
- Hub functions with hundreds of callers (`memcpy`, `malloc`, error handlers) → handled on both sides: their own caller table is suppressed (D7), and they sort into the collapsed utility group in others' callee tables (D34). See §7.2.
- A legitimately important **high-fan-in dispatcher** misclassified as utility → demoted but never hidden; the analyst expands the group, sees it, and can pin the classification with the manual override (D36). This is the accepted cost of the fan-in heuristic.
- A utility function that is itself the **card's root** (analyst navigated directly to `memcpy`) → rendered as a normal card. Demotion applies to *rows*, not to cards; the root is never demoted.
- Fan-in computed at ingestion, then re-ingestion changes it → `is_utility` recomputes, but `utility_override` wins and is preserved (A3, B5a).
- `UTILITY_FANIN_THRESHOLD` changed in config → classification updates without re-ingestion (F1b).
- A function with hundreds of **callees** (a big dispatcher / `switch` jump table) → the callee table is never suppressed, but it scrolls at the row cap and gains filter/sort. Summaries are requested lazily as rows scroll into view, not for all 300 at once.
- Orphan functions with no callers and no callees → single card with two empty-state tables.
- Duplicate edges from multiple call sites → **one row** per callee, not one per call site. Call-site count is deliberately not surfaced (D30).
- Indirect calls / vtables / jump tables → Ghidra often yields no edge. Tables will be **incomplete**; the callee table must carry a footer hint ("may be incomplete — contains indirect calls") rather than implying the list is exhaustive. This matters more now: an explicit table reads as authoritative in a way a graph does not.
- Edge pointing at a function absent from the ingested module (calling into a DLL when only the EXE was analysed, or vice versa) → **ingestion creates a `placeholder` function row** (B17), so the call is always visible and FK integrity holds. The row is fannable and summarisable from its name; a later ingestion of that module upgrades the row in place. A6 on-demand ingest is an optimisation on top of this, not a prerequisite.
- The same external function reached from two binaries → two placeholder rows, one per `binaries` row. Placeholders are never shared across binaries; identity stays `binary_id` + address.
- A placeholder that accumulates high fan-in (e.g. `memcpy` as an import) → classified `utility` by the ordinary rule; no special case.

**Naming & identity**
- Thousands of `FUN_00401a20` names → search must accept addresses; UI should not assume meaningful names.
- Duplicate/ambiguous names across binaries or from overloading/mangling → identity is always `binary_id` + address, never the name.
- Two functions given the **same analyst name** → permitted with an inline warning; `name_analyst` is a label, not a key.
- Analyst renames a function, then re-ingestion changes the Ghidra name → analyst name wins and is preserved (A3); the detail panel shows the new Ghidra name alongside.
- C++ mangled names → assumption: display mangled by default, demangling is a **Could**.
- Very long names/signatures, including analyst-supplied ones → truncate with tooltip; never break layout. Assumption: cap `name_analyst` at 128 chars.
- Empty-string rename → treated as "reset to Ghidra name", not as a blank name.

**Callstack input (simplified format)**
- Input is a newline-separated list of addresses; **each line is assumed to call the next** (D17). No debugger-specific parsing.
- Tolerate cosmetic noise per line: `0x` prefix or none, leading/trailing whitespace, blank lines, and a trailing `+0x1f` offset → assumption: strip and use the base address.
- Address falls **inside** a function rather than at its entry (return addresses normally do) → resolve to the *containing* function, which is the common case and must be the default behavior.
- Address in no known function (other module, dynamically generated code) → unresolved placeholder; the chain shows a gap rather than silently joining the two neighbors.
- Two adjacent lines with no `edges` row between them (indirect call, or a skipped/inlined frame) → render a **dashed "implied" edge** rather than pretending a direct call exists.
- Repeated addresses (recursion in the stack) → the same function appears once on the canvas; the implied path may revisit it. Do not create duplicate nodes.
- Stack pasted innermost-first vs outermost-first → **Reverse order** toggle with preview.
- Duplicate consecutive addresses → collapse.
- A single-line paste → valid; renders one node.

**LLM & summarization (heightened by auto-summarize, C2)**
- **Cost blowout is the primary risk of C2, and the tables change its shape:** placing a single card now demands summaries for that function *plus every visible row in both its tables* — potentially ~33 summaries for one click at default thresholds. Mitigated by: D7 caller suppression (the biggest single win), row virtualisation so only rendered rows are queued (C2a), lazy queueing on scroll, and the concurrency cap (C5). **Lowering `TABLE_ROW_CAP` is also a direct cost lever**, which is a further argument for keeping it configurable.
- **Fan-out itself is free**, by design: the row was already summarised before the user clicked. The cost is paid at card placement, not at fan-out. This is a deliberate property worth preserving.
- Opening a card whose callee table has 300 rows → must **not** enqueue 300 generations. Only rendered rows, plus a small lookahead buffer.
- Scrolling a long table quickly → debounce row-summary requests so a fast scroll-through does not enqueue every intermediate row.
- Rapid expand-then-hide churn, or collapsing a table section → queued-but-unstarted work for now-hidden rows must be cancelled, not merely ignored.
- Provider timeout, rate limit, 5xx, auth failure → distinct error messages, exponential backoff, no poisoned cache.
- A rate-limit error while 12 summaries are queued → back off the whole queue, not per item; surface one banner instead of 12 card errors.
- Decompiled C exceeding the context window → assumption: the adapter (user-owned) handles truncation; GraphRev records that truncation occurred if the adapter reports it.
- Empty/failed decompilation (thunks, imports, obfuscated code) → still request a summary; flag low confidence.
- Hallucinated or wrong summaries → **Regenerate** (C7) plus analyst notes (B7) as the human-authored corrective; notes are never overwritten by regeneration.
- Prompt injection from attacker-controlled strings inside the binary → treat all binary content as untrusted data, never as instructions. Note: prompt hardening is user-owned, but the risk is recorded here.
- Same function requested twice concurrently (two views, double click) → de-duplicate by function id; one in-flight generation per function, ever.
- Summary completes for a function that is no longer visible in any view → still cached (the work is paid for), no UI update needed.
- Browser closed mid-queue → server-side queue state is authoritative (C5a); on reopen, pending items resume or are re-derived from `summary_status`.
- **Server restarted mid-queue** → in-memory queue contents are lost, so rows stranded at `pending` are reconciled at startup (C5b). No function may be left displaying "Analyzing…" forever with nothing generating it.
- A summary completes while its card is off-screen, collapsed, or in a different view → the SSE event still arrives and is applied to the cached function state, so the value is already there when the surface becomes visible again (E5a). No re-request.
- The same function visible as a card in one place and a table row in another → one generation, one event, both surfaces update together (E5a).

**Ingestion & data**
- Very large binaries (100k+ functions) → search must be indexed; never load all nodes; assumption: v1 target is ≤ 50k functions.
- Ingestion interrupted midway → resumable, no partially-written function rows.
- Re-ingestion must preserve `summary_*`, `name_analyst`, and `notes` (A3). Losing an analyst's notes is the single worst data-loss failure this product can have.
- Re-ingestion after a rebuild: addresses shift, names change → assumption: v0 treats a new version as a new `binaries` row; cross-version carryover of summaries/names/notes is out of scope.
- Stripped binaries, packed/obfuscated code, non-x86 architectures → must not crash ingestion; skipped items are reported.
- Same binary ingested twice under different names → two `binaries` rows; acceptable, user-managed.

**Views & multi-binary**
- Deleting a binary → cascades to its functions, edges, and views. Requires explicit typed confirmation given the notes it destroys.
- A view referencing a function deleted by re-ingestion → the stale `view_nodes` row is dropped silently.
- Duplicating a view → copies layout/visibility/colors only; summaries, names, and notes are shared by reference, not copied.
- A view with zero visible nodes → falls back to the canvas empty state, not a blank screen.
- Switching binaries while summaries are in flight → generations continue (they are function-scoped); the queue chip reflects work across binaries.
- Hundreds of views → assumption: not a real scenario; simple list UI is sufficient.

**UI/session**
- Two browser tabs editing the same view → last-write-wins; assumption: acceptable for v0. Notes are the risky case — assumption: debounced autosave with last-write-wins is tolerable for a single-user tool.
- Notes edited while a summary regenerates → independent fields, no conflict.
- Node dragged far off-canvas → **Fit to view** always recovers.
- Hundreds of visible nodes → far less likely now that every node is hand-placed; the realistic path there is repeated callstack imports. Soft warning above `NODE_COUNT_SOFT_WARNING` retained as a backstop.
- Many tall cards at once → virtualise row rendering for off-screen cards; a card scrolled out of the viewport need not render a full table.
- Browser reload mid-generation → pending states reconcile from server status, not from client memory.

### 5.2 Explicitly OUT of Scope

**v0 (UI-validation milestone) — out of scope:**
- Real Ghidra integration (mocked adapter only).
- Real LLM calls (mocked adapter only).
- **Prompt design and prompt engineering** — user-owned, outside this document. GraphRev defines only the adapter contract.
- Authentication, multi-user, or any sharing/collaboration.
- Migrations, deployment packaging, containerization.
- Cost tracking.

**v1 and the product overall — permanently or long-term out of scope:**
- **Being a decompiler or disassembler.** GraphRev consumes Ghidra output; it never performs its own analysis.
- **Editing the binary or patching.** Read-only, always.
- **Basic-block / control-flow graph visualization.** The whole premise is function-level abstraction. Explicitly rejected.
- **Full-fidelity code viewing/editing UX** (syntax-aware navigation, xref browsing inside code, variable retyping) — that is Ghidra's job; deep links back to Ghidra are the integration point.
- **Debugger integration / dynamic analysis / emulation / sandbox execution.** Callstacks are consumed as pasted text only.
- **Automated vulnerability detection or exploitability scoring.** Summaries may note security-relevant behavior; the product makes no verdicts.
- **Data-flow / taint analysis engine.**
- **Automated report generation** beyond Markdown export of summaries and notes (D29).
- **Per-row call-site counts** (D30). One row per unique callee; call frequency is not surfaced.
- **Drag-and-drop of table rows onto the canvas** (D31). Fan-out is a click.
- **Binary diffing across versions** (deferred, D32).
- **Real-time multi-user collaboration** (deferred, D33).
- **Support for non-Ghidra frontends** (IDA, Binary Ninja, radare2) — the adapter interface should not preclude it, but no implementation.
- **"Open in Ghidra" deep links.** Explicitly not needed — the user does not round-trip to Ghidra from the graph.
- **Local / offline LLM hosting**, model fine-tuning, or training on binaries. There are no privacy constraints on this product; a cloud API is acceptable by design.
- **Debugger-specific callstack parsing** (WinDbg/gdb/VS formats). Input is a plain ordered address list, full stop.
- **Telemetry / analytics instrumentation.** Success is judged qualitatively (§1.4).
- **Mobile / small-screen layouts.** Desktop-first, wide viewport assumed.
- **Storing or shipping binaries themselves.** Only extracted artifacts live in the DB.
- **Rich text, threading, timestamped entries, or attachments in notes.** One plain-text field per function, nothing more.

---

## 6. Assumptions Register

Resolved items from v0.1 are marked ✅ **decided**; remaining open assumptions are unmarked.

| # | Assumption | Risk if wrong |
| --- | --- | --- |
| AS1 | Single-user, locally-run tool for v0/v1; no auth needed. Views are scoped to "the user" implicitly. | Rework for tenancy — mitigated, since `views` is already the seam. |
| AS2 | ✅ **Decided:** UI state is scoped to a **view**, not global per function. Summaries, analyst names, and notes are function-scoped and shared across views. | — |
| AS3 | Desktop browser, ≥ 1440 px wide. | Layout redesign. |
| AS4 | Ghidra ingestion is offline/batch; the UI never blocks on Ghidra. | Need synchronous Ghidra bridge (A6 promotes to Must). |
| AS5 | LLM latency is 2–15 s per function; async UX is mandatory. | Simpler sync flow would have sufficed. |
| AS6 | ✅ **Decided:** `summary_short` = 1–3 lines, `summary_long` ≈ 5 lines. Cards reserve 3 lines. | — |
| AS7 | ✅ Addresses stored as integers; hex is a display concern. | Migration. |
| AS8 | Native x86/x64 PE and ELF binaries are the target; C/C++ origin. | Managed (.NET/Java) or embedded targets would need different extraction and prompts. |
| AS9 | ✅ **Decided:** no privacy requirements; cloud LLM APIs are acceptable. No local-model path. | — |
| AS10 | ≤ 50k functions per binary in v1. | Search and neighborhood queries need heavier indexing/pagination. |
| AS11 | "Version" on `binaries` is a free-text label, not a semantic key. | Version-aware features need structure. |
| AS12 | ✅ **Decided:** multi-binary support is in v0; the mock adapter generates ≥ 2 synthetic binaries. | — |
| AS13 | ✅ **Decided:** no telemetry. Outcome metrics are qualitative; only engineering metrics are measured (§1.4). | Cannot quantify adoption — accepted for a personal/team tool. |
| AS14 | ✅ **Decided:** prompt content and real LLM implementation are user-owned; GraphRev owns only the adapter contract, cache, queue, and status model. | If the adapter contract is wrong-shaped, prompt work is constrained. Validate the contract early. |
| AS15 | ✅ **Decided:** callstack input is an ordered address list where each line calls the next. Addresses resolve to their *containing* function. | If real pastes include module names or symbols, a small pre-parse step is added. |
| AS16 | ✅ **Decided:** analyst notes are a **single plain-text field** per function — one textarea, no threading, no timestamps, no rich text. | If a running log is wanted later, notes become a child table (deferred by choice). |
| AS17 | A rename sets a display label only; it never propagates into the stored decompiled C or assembly text. | If users expect variable/function renaming to flow into code, that is a Ghidra-side operation and out of scope. |
| AS19 | ✅ **Decided:** analyst names stay internal to GraphRev; no export/import to Ghidra in v1. | Renames are a per-tool asset, not a portable one; revisit if users start renaming heavily. |
| AS20 | ✅ **Decided:** views persist root + camera (pan/zoom), not just node positions. | — |
| AS18 | Auto-summarize (C2) applies to canvas cards **and visible table rows**; row-level virtualisation and D7 suppression are the brakes. | Runaway cost; may need a per-session budget cap. |
| AS21 | ✅ **Decided:** neighbours are listed in on-card tables; only explicit fan-out places canvas nodes. No automatic 1-hop expansion. | — |
| AS22 | ✅ **Decided:** row cap (default **16**) and caller suppression (default **32**) are **configurable**, not fixed. Callee tables are never suppressed. Defaults are explicitly guesses to be re-tuned on real binaries. | Low — retuning is a config change, not a code change. |
| AS23 | Card width is fixed; only height varies with table content. Max realistic card height ≈ 700 px at the default row cap. | If cards feel unwieldy at zoom, lower `TABLE_ROW_CAP` — no redesign needed. |
| AS24 | ✅ **Decided:** one row per unique callee; call-site count is not surfaced. | Loses call-frequency signal ("12× in a loop" vs. "once in an error path"); accepted deliberately. |
| AS25 | ✅ **Decided:** fanned-out cards open in the default table state; no inheritance of collapse/filter state from the originating card. | — |
| AS26 | ✅ **Decided:** the sidebar stays minimal (search + on-canvas list + legend); it is not a second navigation surface. | — |
| AS27 | ✅ **Decided:** utility functions are **demoted, not hidden** — sorted to the bottom of callee tables in a collapsed group — and **are still summarised**. | — |
| AS28 | ✅ **Decided:** classification is **fan-in threshold** (`fan_in > 50`), computed at ingestion, behind a swappable predicate. | Will misclassify some dispatchers; mitigated by demote-not-hide plus manual override (D36). Sharper classifiers are future experiments. |
| AS29 | Fan-in is a stable enough proxy for "uninteresting" across binary sizes to use one absolute default threshold. | A 200-function binary and a 50k one may need different values; it is config, so cheap to adjust (V2). |
| AS30 | ✅ **Decided:** table collapse/filter/sort/"Show anyway" state is **ephemeral**, reset on reload. | Analysts who curate a card's table state will re-do it each session. Accepted for simplicity; promoting it to `view_nodes` columns is additive. |
| AS31 | ✅ **Decided:** canvas edges come from **fan-out provenance only**, not from the full edge set between visible nodes. | The canvas is an incomplete picture of real call relationships — accepted, because the tables are the authoritative record and the canvas is a record of reasoning. Revisit if analysts report "missing" edges as confusing. |
| AS32 | ✅ **Decided:** `root_function_id` means **last-focused function**; after a callstack import it is the last frame. Nothing in the graph model depends on it. | Low — it is a UI hint only. |
| AS33 | ✅ **Decided:** the **client** requests one summary per rendered row, keyed by function id; the neighbour endpoint has no side effects. | If the client under-requests, rows stay unsummarised; if it over-requests, cost rises. The queue chip makes both visible. |
| AS34 | ✅ **Decided:** unresolved call targets become **placeholder function rows** at ingestion, upgradable in place. | Placeholder rows inflate function counts and fan-in statistics slightly; acceptable, and arguably correct since the calls are real. |
| AS35 | ✅ **Decided:** `kind` is `normal` by default, with `import`/`thunk`/`external` set when the adapter supplies them and `placeholder` for B17. | If Ghidra's classification proves unreliable, the utility classifier does not depend on it (D34a uses fan-in). |
| AS36 | ✅ **Decided:** **SSE only** for async delivery, and **no concurrency control** — one user, one tab, last-write-wins throughout. | A second tab can silently overwrite view state or notes. Accepted deliberately for a local single-user tool; the fix (a version column) is additive. |

---

## 7. Resolved Decisions & Remaining Questions

### 7.1 Resolved (v0.2)

| # | Question | Decision | Requirements affected |
| --- | --- | --- | --- |
| Q1 | Layout ownership | Scope UI state to a **view/workspace/user**; `views` + `view_nodes` tables | B1, B4, B8, B9, D21 |
| Q2 | Auto-summarize vs. click | **Auto-summarize on load**, no click; no "Analyze" button | C2, C2a, C7, C8, E5 |
| Q3 | Summary quality/prompt | User-owned; **mock only** in GraphRev. `summary_short` 1–3 lines, `summary_long` ≈ 5 lines | C1, C4, AS14 |
| Q4 | Callstack formats | **Ordered address list**, each line calls the next; no debugger parsing | D17, E6, AS15 |
| Q5 | Multiple binaries | **Yes, in v0** | A7, AS12 |
| Q6 | Hub handling | **Demote, don't hide:** utility rows sort to the bottom of callee tables in a collapsed `utility calls (N)` group, **still summarised**. Classified by **fan-in threshold** (default 50), behind a swappable predicate | A7a, B5a, C2b, D34–D37, E2b, F1a, F1b, AS27–AS29, §7.2 |
| Q7 | Ghidra deep-link | **Not needed** — removed from scope | §5.2 |
| Q8 | Data sensitivity | **No privacy requirements**, cloud LLM fine, no local mode | §5.2, AS9 |
| Q9 | Success measurement | **No telemetry.** Qualitative outcome bar + measurable engineering metrics | §1.4, AS13 |
| Q10 | Renames | Ghidra name is the default and is **never overwritten**; analyst can set an alternative name that becomes the display name and feeds the prompt | B6, B11, B13, D19 |
| Q11 | Notes *(new)* | Analyst notes are a **Must**: per function, shared across views, autosaved | B7, D20 |
| Q12 | Notes structure | **Simple textarea / single string.** No log, no threading, no rich text | B7, D20, AS16 |
| Q13 | Rename export | **Not needed now.** Analyst names stay internal to GraphRev | B14 (→ Won't, v1), AS19 |
| Q14 | View camera state | **Remember it.** Views persist root function + pan + zoom, not just node positions | B10, D12, E3a, AS20 |
| Q15 | Row cap / caller threshold | **Configurable, not fixed.** Defaults 16 / 32, tunable via config; explicitly assumptions to be re-tuned on real binaries | D6, D7, D7a, F1a, AS22 |
| Q16 | Call-site count per row | **Not needed.** One row per unique callee | D30 (→ Won't), AS24 |
| Q17 | Fanned-out card state | **Default state, no inheritance** of collapse/filter from the originating card | D8a, AS25 |
| Q18 | Sidebar scope | **Keep minimal.** On-canvas list + legend only; no browsable function tree | D21a, AS26 |
| Q19 | Drag-and-drop fan-out | **Not now.** Click-only fan-out | D8, D31 (→ Won't) |

### 7.1a Resolved (v0.7 — TAD-readiness)

Eight gaps found while checking the PRD against the state matrix. All eight answers were simplifications.

| # | Question | Decision | Requirements affected |
| --- | --- | --- | --- |
| Q20 | Where does per-table UI state live? | **Nowhere — it is ephemeral.** Section collapse, utility-group toggle, "Show anyway", filter and sort are session-only and reset to defaults on reload | B4a, §4.2, §4.3, AS30 |
| Q21 | How are canvas edges determined? | **Fan-out provenance only.** An edge exists iff one visible node was fanned out from the other, or the pair is consecutive in an imported callstack. Not derived from the full `edges` table | B4b, D8b, AS31 |
| Q22 | What does `root_function_id` mean? | **Last-focused function**; after a callstack import, the last frame. A camera/orientation hint only | B10a, AS32 |
| Q23 | Who triggers row summaries? | **The client, one request per function**, for rows it actually rendered. `GET` on the neighbour endpoint has no side effects | C2c, E2, AS33 |
| Q24 | Edges to un-ingested functions? | **Create a `placeholder` function row** at ingestion — essential when only an EXE or only a DLL is analysed. Fannable, summarisable from the name, upgraded in place by later ingestion | B17, D35a, §5.1, AS34 |
| Q25 | Raw or effective `is_utility` on the wire? | **Effective** (override applied), plus `utility_source` so the UI can mark analyst-set classification | E2b |
| Q26 | Realtime transport? | **SSE only.** No WebSocket, no polling fallback; reconcile from `summary_status` on reconnect | E5, AS36 |
| Q27 | Concurrency policy? | **None.** One user, one tab, last-write-wins, no version columns | B18, AS36 |

### 7.2 Resolved — Q6: Hub Handling

**The problem.** Two symptoms, one cause. Functions like `memcpy`, `malloc`, `printf`, and error handlers have fan-in in the hundreds: (a) their own **caller list** is unreadable noise, and (b) they appear as **rows in every other function's callee table**, where they consume the most valuable screen space on the card.

Symptom (a) was already solved in v0.4 by caller-table suppression (D7). Symptom (b) is resolved here.

**Decision — demote, don't hide (D34, D35):**

| Aspect | Decision |
| --- | --- |
| Presentation | **Sort utility rows to the bottom** of the callee table, grouped under a collapsible `▸ utility calls (7)` sub-header, collapsed by default. |
| Completeness | Nothing is removed. The count is always visible, and one click expands the group — the table stays authoritative (§5.1). |
| Auto-summary | **Still generated**, exactly as for any other row. Utility rows are demoted for *attention*, not excluded from analysis. |
| Classification | **Fan-in threshold**: a function is `utility` if its caller count exceeds `UTILITY_FANIN_THRESHOLD` (default 50). |
| Storage | Computed once at ingestion into a `fan_in` column plus a derived `is_utility` flag; not recomputed per query. |

**Why keep the summaries** (a change from my earlier leaning): skipping them would have been the largest single cost saving, but it breaks the product's core promise — that *every* function on screen carries meaning. A collapsed group of 7 unsummarised rows would be a dead end precisely when an analyst expands it to check whether a `memcpy` call is the interesting one. Cost is already controlled by D7 suppression, row virtualisation, and `TABLE_ROW_CAP`; and because collapsed groups are not rendered, virtualisation means their summaries are **queued lazily on expand** anyway (C2b). The cost is deferred rather than spent.

**Why fan-in threshold**, of the seven candidates below: it is the only option that needs no new data source, works on stripped binaries, and reuses the caller-count machinery D7 already requires. Its known weakness — misclassifying legitimately important high-fan-in dispatchers — is mitigated by demoting rather than hiding, and by the manual override (D36). Alternatives remain available as future experiments:

| Strategy | Status | Trade-off |
| --- | --- | --- |
| Do nothing | Rejected | Every session starts with manual cleanup |
| **Fan-in threshold** | ✅ **Chosen for v0** | Arbitrary cutoff; may demote important dispatchers — acceptable because demotion is reversible and non-destructive |
| Leaf + fan-in heuristic | Future experiment | Sharper (spares dispatchers), but misses thin wrappers |
| Import/thunk classification (Ghidra `kind`) | Future experiment | More principled, needs A8; statically-linked libc still looks like user code |
| Known-name list | Future experiment | Fails on stripped binaries |
| Library signature matching (FLIRT-style) | Out of scope | High effort |
| Semantic demotion to edge chips | Superseded | The sub-group achieves the same attention fix more simply |

The classifier is deliberately isolated behind one function so these can be swapped without touching the UI (D34a).

### 7.3 Remaining Open

**No open product questions remain.** Q1–Q19 are resolved in §7.1, Q6 in §7.2, and Q20–Q27 in §7.1a. M0 is fully specified and ready for technical design.

Three things to *learn* during M0 rather than decide now — all tuning, not redesign, because each is a config value (F1a):

| # | To validate on a real binary | Lever if wrong |
| --- | --- | --- |
| V1 | Do `TABLE_ROW_CAP = 16` / `CALLER_SUPPRESS_THRESHOLD = 32` feel right? | Config change |
| V2 | Does `UTILITY_FANIN_THRESHOLD = 50` catch `memcpy`-class functions without demoting real dispatchers? | Config change, or swap the classifier (D34a) |
| V3 | How much of a typical callee table is utility noise? | Informs whether a sharper classifier is worth building |

---

## 8. Proposed Milestones

| Milestone | Scope | Exit criteria |
| --- | --- | --- |
| **M0 — UI validation** (current ask) | Mock Ghidra adapter (≥ 2 synthetic binaries, realistic fan-in distribution, placeholder targets, and at least one of each `kind`), mock LLM adapter, SQLite schema incl. `views`/`view_nodes` (with provenance columns) and `fan_in`/`is_utility`, FastAPI + SSE, React Flow + ELK canvas, **root-only load with on-card caller/callee tables**, configurable row cap + scroll, configurable caller suppression, **utility demotion into a collapsed group**, **click-only per-row fan-out**, **auto-summarize on load** (cards + visible rows, lazy for collapsed groups) with queue/cancel, all card and table states, address-list callstack import, per-view persisted layout **and camera**, **analyst rename + notes textarea**, minimal sidebar, binary and view switchers. | An analyst can start at `main` on a synthetic binary, read its callee table with utility noise already pushed to the bottom, fan out selectively to ~5 nodes, hit a suppressed hub without the UI degrading, work across two views, and reopen to the exact same screen. All thresholds re-tunable by config without touching component code. |
| **M1 — Real data** | Real headless-Ghidra ingestion (incl. `fan_in` computation), real LLM adapter behind the M0 contract, concurrency + error handling hardening, stale detection, cost visibility. | A real binary is ingested and explored with genuine summaries; no adapter-contract changes needed. **V1–V3 (§7.3) answered with evidence.** |
| **M2 — Analyst ergonomics** | Manual utility override (D36), path highlighting, in-graph filter, table sort/filter, prompt context enrichment (callees + analyst name + notes), Markdown export of summaries and notes. Optionally a sharper utility classifier if V2/V3 show fan-in is too blunt. | Marcus produces a report from GraphRev without leaving the tool, on a real binary, without manual pruning. |

---

## 9. Changelog

**v0.2 (2026-08-21)** — applied user decisions:
- **Views are now first-class.** UI state moved off `functions` into `views` + `view_nodes`; this is a breaking change to the schema in `idea.md`. Summaries, analyst names, and notes remain function-scoped and shared across views.
- **Auto-summarize on load** promoted to Must; the "Analyze" button removed from the design; **Regenerate**, **Cancel**, async delivery, and the queue indicator promoted to Must as its necessary counterweights.
- **Prompt/LLM implementation declared user-owned**; PRD now specifies only the adapter contract. Summary lengths fixed at 1–3 / ~5 lines.
- **Callstack input simplified** to an ordered address list ("each line calls the next"); all debugger-format parsing moved out of scope.
- **Multi-binary support** promoted to Must for v0.
- **Ghidra deep-links** and **local-model support** explicitly removed from scope.
- **Success metrics restructured** into qualitative outcomes + measurable engineering metrics; telemetry declared out of scope.
- **Analyst rename** (`name_analyst`, Ghidra name preserved) and **analyst notes** added as Musts, with a three-tier truthfulness principle in the UX section distinguishing ground truth / LLM output / analyst input.
- **Hub handling (Q6)** retained as the sole open product question, expanded into a decision framework with an interim non-blocking position.

**v0.3 (2026-08-21)** — minor questions resolved:
- **Notes are a single plain-text field** (Q12). No threading, timestamps, or rich text; `notes` is one `TEXT` column behind one textarea with debounced autosave. Added a state-matrix rule that pending keystrokes are flushed when the selection changes, so notes cannot be silently lost.
- **Analyst-name export deferred** (Q13). New `B14` records it as **Won't (v1)** rather than dropping it, since it is the natural follow-up once renaming becomes habitual.
- **Views now persist camera and root** (Q14): `views` gains `root_function_id`, `camera_x`, `camera_y`, `camera_zoom`; pan/zoom persistence lands in what is now `D12`; new `E3a` patches view-level state debounced separately from node state. Added a fallback so an invalid saved camera degrades to fit-to-view instead of framing empty space.
- Module B renumbered (`B10` is now view camera state; former `B10`–`B13` shifted to `B11`–`B15`); `Q10`/`Q11` cross-references updated accordingly.
- **§7.3 collapsed:** Q6 (hub handling) is now the only open question in the document. M0 is unblocked.

**v0.4 (2026-08-21)** — **navigation model change: cards carry neighbour tables.**

This replaces automatic 1-hop expansion with in-card summarised tables plus explicit per-row fan-out. It is the largest change since v0.1 and touches §1.2, §1.3, J2, J4, Module C, Module D, Module E, §4.1, §4.2, §4.3, §5.1, and Q6.

- **Root-only load** (`D3`): selecting a function places **one** card, not a 1-hop subgraph.
- **Neighbour tables** (`D4`, `D5`): each card lists its callees ("Calls") and callers ("Called by") as rows of *name + short summary*.
- **Row cap with internal scroll** (`D6`, default 16): taller cards for busier functions are intentional signal, but bounded.
- **Caller suppression above 32** (`D7`): a `memcpy`-style caller list collapses to one line with "Show anyway". **Callee tables are never suppressed** — a function's own callees are always meaningful, however many.
- **Explicit per-row fan-out** (`D8`, `D9`, `D10`): `⤢` promotes one function to the canvas; `◎` marks rows already present and re-purposes the control to "focus"; clicking a row *body* opens the detail panel without touching the canvas.
- **Cost profile inverted** (`C2a`): the expensive moment moved from *expansion* to *card placement* (one card can demand ~33 row summaries), so row virtualisation, lazy queueing on scroll, and D7 suppression became the cost controls. **Fan-out is now free** — the row was already summarised.
- **API reshaped** (`E2`, `E2a`): the 1-hop subgraph endpoint became a paginated, sortable, filterable neighbour-table endpoint that signals caller suppression without shipping 291 rows.
- **`summary_short` gained a second job** (`C4`): it must read well clamped to a single table row, not just in a 3-line card body.
- **Tables read as authoritative**, so incompleteness from indirect calls must now be stated explicitly in a table footer (§5.1) — a gap a graph view implied more forgivingly.
- **Q6 partially resolved:** hubs can no longer flood the canvas or the caller list. The residual problem is inverted — utility functions as *noise rows inside callee tables* — and is reframed for decision in v0.6. *(The skip-auto-summary part of the leaning recorded here was subsequently rejected — see v0.6.)*
- Module D renumbered throughout (`D1`–`D31` at the time of writing; `D34`–`D37` were added in v0.6); five new open questions added as `Q15`–`Q19`.

**v0.5 (2026-08-21)** — v0.4 follow-ups resolved; all five answers were simplifications:
- **Thresholds are configuration, not constants** (Q15). New `D7a` and `F1a` define `TABLE_ROW_CAP` (16), `CALLER_SUPPRESS_THRESHOLD` (32), `FAN_OUT_ALL_HARD_CAP` (50), `NODE_COUNT_SOFT_WARNING` (150) in one place, surfaced to the frontend — no magic numbers in components. Prose throughout now refers to "the cap"/"the threshold" rather than hard-coded figures. Noted that `TABLE_ROW_CAP` doubles as an **LLM cost lever**, since it bounds how many row summaries a card placement demands.
- **No call-site count** (Q16). Recorded as `D30` **Won't**; `AS24` now states the lost signal ("12× in a loop" vs. "once in an error path") is accepted deliberately.
- **Fanned-out cards open in default state** (Q17). New `D8a` — no inheritance of collapse/filter state; predictability over cleverness.
- **Sidebar stays minimal** (Q18). New `D21a`: on-canvas list + legend only, **no browsable function tree** — card tables plus toolbar search made it redundant. The §4.1 wireframe was redrawn accordingly, and the sidebar is flagged as a candidate for removal if unused.
- **No drag-and-drop** (Q19). Recorded as `D31` **Won't**; `D8` now states fan-out is click-only.
- Module D gained `D7a`, `D8a`, `D21a` and two Won't entries; `D32`/`D33` absorbed the renumbering. New assumptions `AS25`, `AS26`.
- **§7.3 collapsed again:** Q6 (hub handling) is the sole open question. M0 is fully specified.

**v0.6 (2026-08-21)** — **Q6 (hub handling) resolved. No open product questions remain.**
- **Demote, don't hide** (`D34`): utility rows sort to the **bottom** of the callee table under a collapsible `▸ ▫ utility calls (N)` sub-group, collapsed by default. Nothing is removed and the count is always visible, so the table stays authoritative (§5.1).
- **Utility rows keep their summaries** (`D35`, `C2b`) — a reversal of my earlier leaning. Skipping them would have been the biggest single cost saving, but it would break the promise that every function on screen carries meaning, exactly at the moment an analyst expands the group to check whether a `memcpy` call is the interesting one. Cost is instead handled by the existing virtualisation rule: **collapsed groups are not rendered, so their summaries are queued lazily on expand** — deferred, not spent, and no special-casing needed.
- **Fan-in threshold classification** (`D34a`, `AS28`): `fan_in > UTILITY_FANIN_THRESHOLD` (default 50), computed once at ingestion into `fan_in` + `is_utility` (`B5a`, `A7a`). Chosen because it needs no new data source, works on stripped binaries, and reuses the caller-count machinery D7 already requires.
- **Classifier isolated behind one predicate** (`D34a`) so the leaf+fan-in, Ghidra-`kind`, and name-list strategies remain drop-in experiments. The strategy table in §7.2 was rewritten as chosen-vs-future rather than open options.
- **Blunt-heuristic mitigations:** demotion is never destructive, the root card is never demoted, and `D36` adds a persisted per-function manual override (`utility_override`) that survives re-ingestion like notes and names. Threshold changes must not require re-ingestion (`F1b`).
- **API returns rows pre-ordered** with utility last, carrying `is_utility`/`fan_in` (`E2b`), so the client never re-derives grouping.
- **§7.3 replaced** with a V1–V3 validation list — three things to *learn* on a real binary (row cap, utility threshold, how much of a table is actually noise), each fixable by config rather than redesign. M2 now optionally swaps in a sharper classifier if the evidence warrants it.

**v0.7 (2026-08-21)** — **TAD-readiness pass.** A review against the state matrix found eight behaviours that were specified in the UI but had no home in the schema or API. All eight resolutions were simplifications; none changed the product model. New §7.1a records them as Q20–Q27.

- **Per-table UI state is ephemeral** (`B4a`, Q20). Section collapse, the utility-group toggle, "Show anyway", filter text, and sort order are session-only — the state matrix previously implied they persisted, which would have widened `view_nodes` for little gain. §4.2 and two state-matrix rows corrected.
- **Canvas edges come from fan-out provenance only** (`B4b`, `D8b`, Q21). `view_nodes` gains `origin_function_id`, `origin_kind`, `origin_implied`. Two nodes placed independently show no connector even when a call exists — the canvas records the analyst's reasoning, the tables record the call graph. New state-matrix rows cover the independently-placed and hidden-parent cases.
- **`root_function_id` = last-focused function** (`B10a`, Q22), set to the final frame after a callstack import. Previously used three different ways across B10/D3/J5.
- **The client drives summary demand, one request per function** (`C2c`, Q23); `GET` on the neighbour endpoint is side-effect-free. This is what makes virtualisation a genuine cost control rather than a rendering detail, and it gives de-duplication a single key.
- **Placeholder functions are first-class** (`B17`, `D35a`, Q24). Analysing only an EXE or only a DLL is the normal case, so unresolved call targets become real `functions` rows with `kind = 'placeholder'`, upgraded in place by later ingestion. Resolves an unrepresentable state: §5.1 previously described rows that the `edges` foreign keys could not express.
- **`kind` enumerations closed** (Q25/Q26 context): `functions.kind` ∈ {`normal`, `import`, `thunk`, `external`, `placeholder`}, `edges.kind` = `call` in M0. Both columns were previously in the Must schema with no defined values.
- **API returns the *effective* utility flag** plus `utility_source` (`E2b`, Q25), so the client never re-applies `utility_override`. `E2` now takes a required `view_id`, since `on_canvas` is a view fact.
- **SSE only** (`E5`, Q26) — WebSocket and polling dropped; reconnect reconciles from `summary_status`. **No concurrency control** (`B18`, Q27): last-write-wins, no version columns, one tab assumed.
- **Missing Must endpoints added** (`E1`, `E1a`–`E1d`): delete binary, paginated search, suggested entry points, queue state + cancel, and a config endpoint feeding the F1a constants to the frontend. `E6` now also reports which consecutive callstack pairs lack a backing edge, so implied links render dashed. `binaries.last_view_id` (`B16`) backs the "switch to last-used view" behaviour.
- **Background generation hardened** (`C5a`, `C5b`, `E5a`, `E5b`): generation is explicitly a server-owned background worker that never holds the HTTP request open, so work survives the client navigating away or closing the tab; stranded `pending` rows are reconciled on server restart so nothing can display "Analyzing…" forever; and the SSE completion event now **carries the summary itself**, so every surface showing that function patches in place without a refetch or a layout reflow. Two §4.4 principles added — *render what you have, immediately* and *background work is always visible* — plus four §5.1 edge cases (server restart, completion while off-screen, one function on two surfaces).
- **Cleanups:** `C8` clarified (queued-only cancellation, refcounted across views so one view cannot cancel another's work); §4.4's prompt-context reference corrected from `B12` to `B13`; M0 glyph set separated from the D27 **Should** glyphs; the ≤ 20 metric annotated as a median against the ~33 worst case; UTC/ISO-8601 timestamp convention and a fixed color palette stated.

**v0.8 (2026-08-22)** — **bidirectional fan-out: the canvas grows left as well as right.**

The §4.2 card wireframe always showed `⤢` on `CALLED BY` (caller) rows, but caller fan-out was inert in the implementation — only callee rows placed nodes. This makes caller rows fannable and grows the graph *leftward*, so an analyst can walk both up and down the call chain from any card, indefinitely in either direction. A pure additive change; no product model change.

- **New `origin_kind` value `fanin`** (`B4b`, Module-B enum table): like `fanout` but the derived canvas edge is oriented new-node→origin-card rather than origin-card→new-node. Because the layout direction is RIGHT (a source lays out left of its target), a `fanin` node lands to the *left* of the card it was spawned from — no layout-algorithm change, orientation alone does the work.
- **`D8` amended:** fanning out a callee places the new card right (`fanout`); fanning out a caller places it left (`fanin`). **`D8b` amended:** provenance now fixes edge *orientation*, not just existence — this does not weaken the "provenance is the sole source of canvas edges" invariant, it only says which way the arrow points.
- **Rejected alternatives** (see `docs/adr/0005`): rewriting the clicked card's own `origin_function_id` to point at the new caller (breaks with a *second* caller, since `origin_function_id` is a single-parent FK) and a separate `origin_direction` column (a 2-column state space with many invalid combinations). A single widened enum has no invalid states and forces exhaustive handling at every switch site.
