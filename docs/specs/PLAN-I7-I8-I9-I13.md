# Implementation plan — I7, I8, I9, I13 (the asynchronous plane + real LLM)

| Field | Value |
| --- | --- |
| Status | Approved for implementation. Written 2026-08-24. |
| Source of truth | `docs/specs/TAD.md` (§2.6, §2.7, §6.3, §7 I7/I8/I9/I13) and `PRD.md` v0.7 |
| Prerequisite state | I1–I6 complete. I12 partly complete early (file-based Ghidra adapter works). |
| Reader | A fresh agent context with no memory of the design conversation. |

This document is the **complete brief**. It records decisions already taken so
they are not re-litigated, and flags the places where the TAD is deliberately
*amended*. Where this document and the TAD disagree, **this document wins** and
says so explicitly.

---

## 0. Read this first — current repo state (verified, not assumed)

Verified by inspection on 2026-08-24:

| Thing | State |
| --- | --- |
| `backend/src/graphrev/summarization/` | **Empty** — only `__init__.py` |
| `backend/src/graphrev/events/` | **Empty** — only `__init__.py` |
| `backend/src/graphrev/adapters/llm/` | **Empty** — only `__init__.py` |
| `api/routers/` | Has `binaries, config, functions, health, neighbours, view_nodes, views`. **No** `summaries.py`, `queue.py`, `events.py`. |
| `services/` | Has `binary, canvas, function, neighbour, search, view`. **No** `summary_service.py`. |
| `core/hashing.py` | **Does not exist** |
| `db/startup.py` | **Exists** and already implements `recover_pending_summaries()` (the `C5b` sweep) + `recompute_utility_if_threshold_changed()`. Both already wired into `main.py` lifespan. **Do not rewrite these.** |
| `Settings` (`core/config.py`) | Already declares `llm_adapter: Literal["mock","anthropic"]`, `llm_model`, `summary_concurrency=4`, `queue_max_depth=500`, `summary_demand_debounce_ms=250`, `sse_keepalive_seconds=15`, `sse_subscriber_queue_size=256`. I1 pre-wired this. |
| `ErrorCode` (`core/errors.py`) | Already declares `SUMMARY_ALREADY_PENDING`, `SUMMARY_PROVIDER_ERROR`, `SUMMARY_RATE_LIMITED`, `QUEUE_FULL`. |
| `schemas/function.py` | Already has `FunctionSummaryStateDto` with `status/short/long/model/error_code/low_confidence/generated_at/is_stale`. |
| `frontend/src/features/neighbours/SummaryCell.tsx` | Already switches on all five `SummaryStatus` values. Its own comment says shimmer polish "arrives with I9". |
| `frontend/src/features/card/CardSummary.tsx` | Same — handles `pending` already. |
| `frontend/src/store/` | Has `canvasSlice.ts`, `uiSlice.ts`, `index.ts`. **No** `demandSlice.ts`, **no** `tableUiSlice.ts`. |
| `frontend/src/realtime/` | **Does not exist** |
| `frontend/src/api/queries/` | Has `binaries, functions, neighbours, viewNodes, views`. **No** `queue.ts`. |
| Migrations | `0001`–`0004` applied. Next revision is **`0005`**. |

**Consequence:** the UI already renders every summary state correctly. It has
simply never received anything other than `none`. Do not redesign
`SummaryCell`/`CardSummary`; feed them.

### Repo conventions you must follow

Read `/memories/repo/graphrev.md` first — it is the authoritative list. Key items:

- **Closed enums:** `db/enums.py` declares each `Literal` + a `*_VALUES` tuple;
  `db/models.py` derives CHECK constraints from the tuple via `_sql_in_list()`.
  Edit the tuple and the model CHECK follows for free.
  `frontend/src/api/types.ts` **hand-mirrors** these unions (`generated.ts` is a
  stub — openapi-typescript is not actually wired up yet).
- **Tests:** `just test` (backend pytest ~3 min + frontend vitest — slow).
  Single frontend file: `cd frontend && npx vitest run <path>`.
  Frontend typecheck: `npx tsc -b` (**not** `tsc -p tsconfig.app.json`).
- **Known-failing baseline, NOT your regressions:** 4 pre-existing `tsc -b`
  errors and 2 of 3 `CanvasView.test.tsx` vitest failures. The memory file lists
  them exactly. Verify against baseline before believing you broke something.
- **Migrations:** `just revision <name>`, then `just migrate`.
- `exactOptionalPropertyTypes` is on. Spread conditionally
  (`...(cond ? { x } : {})`), never `x: cond ? v : undefined`.
- Layering, enforced by import-linter in CI: `api → services → repositories → db`.
  `repositories` may not import `services` or `summarization`. Nothing outside
  `adapters/*/` may import a concrete adapter impl — only `base`.

---

## 1. Decisions already taken (do not revisit)

1. **Scope is I7 + I8 + I9 + I13**, in that order, in four steps. The user
   explicitly wants live UI updates when analysis finishes, which requires SSE
   (I8). I9 is included because the user wants auto-analysis on card open.
2. **Trigger policy — auto-demand, as I9 specifies.** Opening a function card
   analyses the function itself first, then its callees and callers. Rationale
   accepted by the user: results are cached and function-scoped, so the second
   visit is free and only newly-discovered functions cost anything.
3. **Two real adapters behind one Protocol, indistinguishable to the app:**
   - **A = litellm** (`LiteLlmAdapter`) — summarise from decompiled C/assembly.
     Chosen over routing A through opencode because **litellm can enforce a JSON
     schema on the response and opencode cannot**. A is the high-volume
     structured-output path; reliability matters more than uniformity.
   - **B = opencode** (`OpenCodeAdapter`) — an agent with ghidra-MCP access.
4. **`opencode serve` IS the sidecar.** Do **not** build a custom bridge web
   service. It is a headless HTTP server with an OpenAPI spec. The backend needs
   only `httpx` — no Node/`claude-code` runtime dependency.
5. **Binary identity check is deliberately loose.** Compare the **exe filename
   only**. The user explicitly said making certain it is the same exact file is
   over-engineering for now and to trust the operator. So: no
   `binaries.ghidra_program_name` column, no hashing. Filename mismatch → fail
   with a clear error; anything subtler is out of scope.
6. **Record which adapter produced each summary, but do not surface it in the
   UI yet.** Migration `0005` adds `functions.summary_adapter TEXT`. Expose it
   on the DTO (cheap, and it makes the data self-describing for later analysis),
   but add **no** UI affordance.
7. **Deferred by the user:** speed/cost tuning of LLM usage. Do not build
   budget caps, spend meters, or `C11` cost tracking beyond logging.

---

## 2. Amendments to the TAD (intentional divergences)

State these in code comments where they apply, so a later reader does not
"fix" them back to the TAD text.

| # | TAD says | This plan does | Why |
| --- | --- | --- | --- |
| **AM1** | `LlmAdapter` Protocol is `async def summarize(req)` only (§6.3) | Add `max_concurrency: int` to the Protocol. Worker pool size = `min(settings.summary_concurrency, adapter.max_concurrency)` | The ghidra-MCP bridge drives **one** loaded program. `OpenCodeAdapter` must declare `1`; four parallel agents on one Ghidra instance is a correctness hazard, not just slow. The TAD's flat `summary_concurrency=4` assumes every adapter is stateless. |
| **AM2** | `SummaryRequest` carries `address, name, parameters, code_c, assembly, analyst_name, notes, callee_summaries` (§6.3) | Also carry `binary_name`, `binary_version`, `source_path` | B needs to tell the agent *which program* to drive. Adding it in **I7** means I13 needs no protocol change — the same discipline the TAD already applies to `notes`/`callee_summaries` (which the mock ignores). §7.1's risk register explicitly demands "no protocol change" at I13. |
| **AM3** | `LlmAdapterName = Literal["mock","anthropic"]` | Becomes `Literal["mock","litellm","opencode"]` | `"anthropic"` is currently declared but unused and unimplemented. Replace it rather than accumulate a dead variant. Closed-enum discipline (`docs/adr/0004`) means this is a deliberate edit. |
| **AM4** | `functions` has no adapter provenance column | Migration `0005` adds `summary_adapter TEXT` (nullable, **no** CHECK) | Decision 6. Nullable + no CHECK keeps it a plain `ADD COLUMN`: safe despite the VIRTUAL generated column `is_utility_effective`, which would otherwise force a batch table rebuild (see the SQLite notes in repo memory). |
| **AM5** | `GET /health` returns `llm_adapter` name only | Also report opencode reachability + ghidra-MCP connection status when `llm_adapter == "opencode"` | The UI must be able to tell "no summaries because misconfigured" from "no summaries yet". Without this the failure mode is a silent stall. |
| **AM6** | Ephemeral table state lives in `store/tableUiSlice.ts` (§5) | Not created by this work | It does not exist yet and I9 does not need it. Do not invent it here; it belongs with whichever increment actually needs collapse/filter persistence. Note it as still-missing. |

---

## 3. Step 1 — I7: LLM protocol, queue, worker, endpoints

Ship entirely against `MockLlmAdapter`. **No network, no API key, no opencode.**
This step must be fully testable in CI.

### 3.1 `adapters/llm/base.py`

```python
@dataclass(frozen=True, slots=True)
class SummaryRequest:
    address: int
    name: str
    parameters: tuple[RawParam, ...]
    code_c: str | None
    assembly: str | None
    analyst_name: str | None          # B13
    notes: str | None                 # B13
    callee_summaries: tuple[tuple[str, str], ...]   # C9 (name, summary_short)
    # AM2 — present from I7 so I13 needs no protocol change:
    binary_name: str
    binary_version: str
    source_path: str | None

@dataclass(frozen=True, slots=True)
class SummaryResult:
    summary_short: str        # MUST clamp to one table row (C4)
    summary_long: str
    model: str
    low_confidence: bool = False
    input_truncated: bool = False

class LlmAdapter(Protocol):
    @property
    def max_concurrency(self) -> int: ...   # AM1
    @property
    def name(self) -> str: ...             # -> functions.summary_adapter (AM4)
    async def summarize(self, req: SummaryRequest) -> SummaryResult: ...
    async def health(self) -> LlmHealth: ...  # AM5
```

Error taxonomy exactly per TAD §6.3 — the worker's whole retry policy is driven
by these types and nothing else:

```
SummarizationError
├── TransientProviderError   → retry ×3, exponential backoff + jitter
├── RateLimitError           → pause the WHOLE queue until retry_after
├── AuthError                → fail fast, do not retry
├── ContextTooLargeError     → fail with a specific code; adapter owns truncation
└── PermanentProviderError   → fail, cache nothing (C6)
```

Follow the `adapters/ghidra/base.py` docstring style — it explains *why* the
Protocol exists and which import-linter contract guards it. Mirror that.

### 3.2 `adapters/llm/mock.py`
`MockLlmAdapter`: 1–8 s latency, ~5 % failure, seeded PRNG so CI is
deterministic (`C1`). `max_concurrency = 4`, `name = "mock"`.
Make the failure injection *controllable* (a seed or an explicit
`fail_on: set[int]`) — the API tests need a fake that fails on command.

### 3.3 `summarization/queue.py`

`SummaryQueue` per TAD §2.6 — implement all of it:
- `asyncio.PriorityQueue` of `QueueItem(priority, seq, function_id, demand)`.
- Priorities 0–3: 0 selected card's own summary, 1 selected card's visible rows,
  2 other visible cards, 3 off-screen/lookahead.
- **Dedup:** `_index: dict[int, QueueItem]`, one item per `function_id` ever.
- **Priority upgrade:** mark-stale-and-reinsert; discard the stale copy on pop.
- **Refcounted advisory cancel:** `DELETE` decrements `demand`; drop only at
  `demand == 0` **and** not in `_inflight`. In-flight always completes (`C8`).
- **Bounded** at `queue_max_depth`; overflow evicts lowest-priority-oldest + logs.
- **Queue-wide pause** on `RateLimitError` (`_paused_until`) → **one** banner.

> Build the `demand` refcount and `DELETE` now even though nothing calls
> `DELETE` until Step 3. The I7 exit test asserts `DELETE` cancels a queued
> item, and it is cheap.

### 3.4 `summarization/worker.py`
N asyncio tasks, `N = min(settings.summary_concurrency, adapter.max_concurrency)`
(AM1). Each task: pop → load context → `adapter.summarize()` → persist → publish.

Persist on success: `summary_short`, `summary_long`, `summary_status='ready'`,
`summary_model`, `summary_adapter` (AM4), `summary_generated_at`,
`summary_input_hash`, `summary_low_confidence`, clear `summary_error_code`.
On failure: `summary_status='error'` + `summary_error_code`, cache nothing (`C6`).

Write through `db/uow.py` (process-wide write lock — SQLite single-writer).
Log one structlog line per call with `event, function_id, binary_id, duration_ms,
adapter, model, outcome` (§6.4 — these fields are how §1.4 metrics get computed,
since there is no telemetry).

Wrap each call in `asyncio.timeout` — a hung adapter must not wedge a worker
permanently. Especially relevant once B (minutes-long agent runs) exists.

### 3.5 `summarization/context.py` (`C9`) and `core/hashing.py` (`C10`)
`context.py` assembles `SummaryRequest` from DB rows including callee
`summary_short` values. **Prompt content is out of scope** (`AS14`) — this module
assembles *data*, never phrasing.

`core/hashing.py`: `summary_input_hash` over the inputs that would invalidate a
summary (code, name, notes). Stable and order-independent.

### 3.6 Recovery
**`db/startup.py::recover_pending_summaries` already exists and is already
wired into the lifespan.** Do **not** create `summarization/recovery.py`; do not
duplicate the sweep. Just confirm it still runs before workers start.

### 3.7 Service + routers
- `services/summary_service.py` — request/cancel/regenerate façade, cache-first
  (`C3`).
- `api/routers/summaries.py` — endpoints 17/18/19 (TAD §4.2).
  `POST` returns **202** in <20 ms with `{functionId, summaryStatus, queuePosition}`,
  or **200** with the cached result if already `ready`. It must **never** block.
  `regenerate` forces priority 0, bypasses the cache check, preserves `notes`.
- `api/routers/queue.py` — endpoints 20/21.
- `schemas/summary.py` — the DTOs.
- Register both routers in `main.py`; start/stop the worker pool in the lifespan
  (**after** the existing migration assertion and startup hooks); provide the
  queue + adapter via `api/deps.py` (follow the existing `Annotated[...]` alias
  style there).

Adapter construction goes behind a small factory so only
`adapters/llm/__init__.py` imports the concrete impls — import-linter enforces this.

### 3.8 I7 exit tests (from TAD §7)
- `POST /summary` returns <20 ms with `pending`.
- 50 concurrent requests → exactly N in flight, never more.
- Duplicate request creates **no** second queue item.
- `DELETE` cancels a queued item but **never** an in-flight one.
- Process killed mid-queue then restarted → **zero** rows left at `pending`.
- Simulated rate limit pauses the queue **once** rather than failing 12 items.
- Unit tests for `SummaryQueue` (dedup, priority upgrade, refcount cancel,
  bound, pause) and `summary_input_hash`.

---

## 4. Step 2 — I8: SSE end to end

### 4.1 Backend
- `events/bus.py` — `EventBus` Protocol + `InProcessEventBus`. Each subscriber
  gets a bounded `asyncio.Queue(maxsize=settings.sse_subscriber_queue_size)`.
  **On overflow, close the connection with a `reconcile` hint** rather than
  silently dropping events. Silent drops are how a client ends up permanently
  showing a stale `pending`.
- `events/sse.py` — event-stream generator, `: keepalive` every
  `sse_keepalive_seconds`, monotonic `id:` per event (enables a future replay
  buffer additively; M0 does not replay).
- `api/routers/events.py` — `GET /events` with `Content-Type: text/event-stream`,
  `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- Event types: `summary`, `queue`, `binary`, `reconcile`. **`summary` carries the
  full result** (`E5a`) so every surface patches in place with no refetch.
- `schemas/events.py` for the payloads.

**TQ2 (open in the TAD): `sse-starlette` vs. hand-rolled.** Decide by reading
the dep, and **write `docs/adr/0005-sse-transport.md`** either way — the TAD
requires an ADR for this choice.

### 4.2 Frontend
- `realtime/SseProvider.tsx` — `EventSource` lifecycle, reconnect, reconcile.
- `realtime/applyEvents.ts` — `applySummaryEvent(qc, e)` exactly as sketched in
  TAD §4.3: `setQueryData(['function', id])` **and** `setQueriesData(['neighbours'])`
  patching the row in **every** cached page. One event, all surfaces.
- Reconnect reconciliation: on `open` after an error, invalidate `['function']`
  and `['neighbours']` and refetch `GET /queue`. Never trust client memory
  across a gap.
- `api/queries/queue.ts`; `features/toolbar/QueueChip.tsx` (`◌ 3 of 12`) +
  popover driving `POST /queue/cancel-pending`. Glyphs come from
  `lib/glyphs.ts` — the single source shared with `docs/glyphs.md`.
- Mount `SseProvider` in `App.tsx`.

### 4.3 I8 exit tests
- One completing summary patches the card **and** the same function's row in a
  *different* card, from a single event, with **no refetch** (network spy) and
  **no layout recomputation** (ELK-call spy). These two spies are the mechanical
  enforcement of **T1** — do not skip them.
- Killing and restoring the stream re-reads authoritative status.
- The chip shows `◌ 3 of 12` and cancel-pending works.

---

## 5. Step 3 — I9: demand registry (auto-analysis)

This is the **cost-control** increment and the PRD's own "primary risk". The
user has accepted auto-demand; the brakes below are what make that safe, and
they are not optional.

### 5.1 Ordering requirement (explicit user instruction)
Opening a function card must analyse **the function itself first**, then its
callees and callers. This is exactly the existing priority ladder — the card's
own summary is priority 0, its visible table rows priority 1 — so implement it
via priorities, **not** by serialising requests client-side.

### 5.2 `store/demandSlice.ts`
```ts
interface DemandRegistry {
  refs: Map<FunctionId, Set<SurfaceId>>;
  acquire(fnIds: FunctionId[], surface: SurfaceId, priority: Priority): void;
  release(fnIds: FunctionId[], surface: SurfaceId): void;
}
```
- `acquire` from `VirtualRowList` with **exactly the rendered indices + 4-row
  lookahead**, debounced `settings.summary_demand_debounce_ms` (250) — the
  fast-scroll guard.
- Never re-request a function already `ready` or `pending` (status comes from the
  Query cache, which SSE keeps current).
- `release` on unmount / section collapse / utility-group collapse / card hide /
  view switch → `DELETE` when the last surface releases.
- Collapsed groups render nothing → never acquire → **deferred, not skipped** (`C2b`).
- **Suppressed caller tables never acquire** (`D7`/`E2a`) — the single biggest
  cost lever, since that is the 291-caller hub case.

### 5.3 `hooks/useSummaryDemand.ts`
Wire into `VirtualRowList`, `UtilityGroup` (lazy acquire on expand),
`FunctionCardNode` (own summary at priority 0), `DetailPanel`.

Then finish the summary states in `SummaryCell`/`CardSummary`: shimmer, queued,
error+retry, stale, low-confidence. The components already branch on status —
this is presentation polish, not new logic.

**`AS36` — single tab assumed.** The registry is per-tab; two tabs double-count
demand. Acceptable, but note it in the module docstring.

### 5.4 I9 exit tests (the cost bound — highest-risk behaviour in the product)
- A card with 300 callees enqueues **≤ `tableRowCap + 4`**, never 300.
- Fast-scrolling the whole table enqueues far fewer than one per row.
- Expanding the utility group enqueues exactly its 7.
- Collapsing it cancels the unstarted remainder.
- Opening a suppressed hub enqueues **only its own** summary.
- Placing one typical card demands **≤ 20** summaries (median) — the §1.4 target.

---

## 6. Step 4 — I13: real adapters

### 6.1 Migration `0005`
`ALTER TABLE functions ADD COLUMN summary_adapter TEXT` — nullable, no CHECK
(AM4). Plain `ADD COLUMN` is safe here; a new CHECK would force a batch rebuild,
which SQLite refuses on this table because of the VIRTUAL generated column.

Then update: `db/models.py`, `schemas/function.py`
(`FunctionSummaryStateDto.adapter`), `frontend/src/api/types.ts` (hand-mirrored).
Confirm `summary_adapter` is **absent** from `INGESTION_OWNED_COLUMNS` — it is
LLM-owned and must survive re-ingestion (`A3`). Extend the existing `A3` test.
`test_schema_snapshot.py` will need its expectation updated;
`test_health.py` asserts the head revision string and will also need updating.

### 6.2 `adapters/llm/litellm_adapter.py` (option A)
- `litellm.acompletion(model=settings.llm_model, api_base=..., api_key=...)`.
  One adapter covers Anthropic / OpenAI / Ollama / vLLM / OpenRouter — which is
  the point, since `V1–V3` require retuning the model by config alone.
- **Enforce structured JSON output** `{summary_short, summary_long,
  low_confidence}` and validate with Pydantic. Never regex a prose blob.
  Hard-clamp `summary_short` to one table row in the adapter (`C4`) — the DB
  column is what the UI trusts.
- Map litellm's normalised exceptions onto the taxonomy: `RateLimitError`,
  `AuthenticationError`, `ContextWindowExceededError`, `APIConnectionError`.
- **Prompt-injection fencing (§5.1, §6.4).** Decompiled C, strings and symbol
  names are **untrusted**. Keep them in delimited data blocks with an explicit
  instruction that content inside is data, never instructions. `AS14` puts prompt
  *wording* out of scope; it does **not** excuse skipping the fence.
- Truncate oversized `code_c` in the adapter, report `input_truncated`, and raise
  `ContextTooLargeError` only if even the truncated form fails.
- `max_concurrency = settings.summary_concurrency`, `name = "litellm"`.

### 6.3 `adapters/llm/opencode_adapter.py` (option B)
Verified opencode HTTP API (`opencode serve`, default `127.0.0.1:4096`,
OpenAPI at `/doc`):

| Need | Call |
| --- | --- |
| Create session | `POST /session` |
| Prompt **and wait for the result** | `POST /session/:id/message` → `{info, parts}` |
| Cancel | `POST /session/:id/abort` |
| Server health | `GET /global/health` |
| Is ghidra-MCP connected? | `GET /mcp` |
| Select the agent | `agent` field in the message body |
| Auth | `OPENCODE_SERVER_PASSWORD` (basic auth, user defaults `opencode`) |

Key consequences — these make B much cheaper than it first appears:
1. `POST /session/:id/message` **blocks and returns the answer**. Our worker
   already runs off-request, so this is a plain `httpx` call. No polling, no
   event-stream parsing, no `/prompt_async`.
2. **No Node runtime dependency** in the backend. Just `httpx` against a port.
3. MCP stays warm under `serve` (the docs recommend `serve` precisely to avoid
   per-run MCP cold boot), so **a fresh session per function is affordable** —
   which is also what we want, to avoid context bleed between functions.

Implementation:
- `max_concurrency = 1` (one Ghidra program, one bridge), `name = "opencode"`.
- **Filename check (decision 5):** before summarising, confirm the loaded Ghidra
  program's filename matches `req.binary_name`. Mismatch → new
  `ErrorCode.GHIDRA_PROGRAM_MISMATCH`, fail fast. Filename only — no hashing.
  This guard matters because a wrong summary is **unrecoverable**:
  `summary_*` is ingestion-immutable by design (`A3`), so re-ingestion will not
  clean it.
- **Bounded agent loop:** `agent_max_tool_calls`, `agent_timeout_seconds` via
  `asyncio.timeout`, read-only tool allow-list. An unbounded agent on a 1-wide
  queue is a permanent stall.
- Mine the returned `parts` for the JSON payload; on unparseable output raise
  `PermanentProviderError` (cache nothing) rather than storing prose.
- Map connection failure → `TransientProviderError`; 401 → `AuthError`.
- `health()` → `GET /global/health` + `GET /mcp` for AM5.

### 6.4 opencode-side config (not Python)
Create `tools/opencode-ghidra/` containing `opencode.json` (the `mcp` block for
the Ghidra bridge) and `.opencode/agent/graphrev-re.md` (read-only permission
set, ghidra MCP tools enabled). `opencode serve` runs with that directory as
cwd. Document startup in `tools/opencode-ghidra/README.md`, matching the style
of the existing `tools/ghidra/README.md`.

### 6.5 Config + health
New `Settings` fields (`F1a` — every one of them, no literals in components):
`llm_api_base`, `llm_api_key`, `opencode_url`, `opencode_agent`,
`opencode_password`, `agent_max_tool_calls`, `agent_timeout_seconds`,
`summary_request_timeout_seconds`.

Widen `LlmAdapterName` to `Literal["mock","litellm","opencode"]` (AM3).

Extend `GET /health` per AM5. Add `GHIDRA_PROGRAM_MISMATCH` to `ErrorCode` and
mirror it in `frontend/src/api/types.ts`.

`scripts/check-magic-numbers.sh` will fail the build if any new threshold gets
hard-coded in a component — respect it rather than working around it.

### 6.6 I13 exit tests
- Both adapters satisfy the Protocol with **no protocol change from I7** — this
  is the actual validation of `AS14` and the §7.1 risk mitigation.
- litellm: malformed JSON, rate-limit, auth-failure and context-overflow
  responses each map to the right taxonomy member and the right
  `summary_error_code`. Use a stubbed transport; **no live API calls in CI**.
- opencode: filename mismatch → `GHIDRA_PROGRAM_MISMATCH` and **nothing is
  written to `summary_*`**. Stub the HTTP layer.
- `summary_adapter` is persisted and survives re-ingestion (extends the `A3` test).
- Updated schema-snapshot + health-revision assertions pass.

---

## 7. Suggested commit boundaries

1. `feat(i7): LlmAdapter protocol, mock adapter, SummaryQueue + unit tests`
2. `feat(i7): worker pool, summary/queue endpoints, lifespan wiring`
3. `feat(i8): EventBus + SSE endpoint + ADR 0005`
4. `feat(i8): SseProvider, cache patching, QueueChip`
5. `feat(i9): demand registry + useSummaryDemand + summary states`
6. `feat(i13): migration 0005 summary_adapter`
7. `feat(i13): litellm adapter`
8. `feat(i13): opencode adapter + filename guard + health`

Steps 1–5 need no API key and no opencode; they must be green in CI on their own.

---

## 8. Traps specific to this repo

- **Do not rewrite `db/startup.py`.** The `C5b` sweep exists and is wired up.
  The TAD's `summarization/recovery.py` is already satisfied elsewhere.
- **`generated.ts` is a stub.** `openapi-typescript` is not wired up. Hand-mirror
  new types in `api/types.ts` and do not assume codegen.
- **Baseline test failures exist.** 4 `tsc -b` errors, 2 `CanvasView.test.tsx`
  failures. Check `/memories/repo/graphrev.md` before diagnosing.
- **`exactOptionalPropertyTypes`** — conditional spreads only.
- **React Flow marks node subtrees `aria-hidden`**, so testing-library role
  queries do not find in-card buttons. Query the DOM directly or use
  `hidden: true`. This will bite the I9 card-level tests.
- **Never let a summary arrival trigger ELK.** Card geometry derives from row
  count, known before any summary exists (**T1**). The ELK-call spy in the I8
  test is what enforces it.
- **`import-linter` will fail the build** if `services`/`summarization` imports a
  concrete adapter, or if `repositories` imports `summarization`.
