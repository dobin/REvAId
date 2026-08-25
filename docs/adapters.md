# Implementing a real adapter (M1 handoff)

GraphRev's Ghidra and LLM integrations are `Protocol`s (TAD §6.3). M0 ships
only mock implementations; this document is the contract a real adapter must
satisfy, so M1 (`I12`, `I13`) can be implemented with zero changes to
`services/`, `repositories/`, or the API surface.

## Ghidra adapter

Implemented as of Increment I2. The authoritative Protocol and DTOs live in
`graphrev.adapters.ghidra.base` — this section is a summary, not a
substitute for reading that module:

```python
class GhidraAdapter(Protocol):
    def list_binaries(self) -> Sequence[RawBinary]: ...
    def iter_functions(self, binary: RawBinaryRef) -> Iterator[RawFunction]: ...
    def iter_edges(self, binary: RawBinaryRef) -> Iterator[RawEdge]: ...
    def get_function(self, binary: RawBinaryRef, address: int) -> RawFunction | None: ...
```

`RawFunction.has_indirect_calls` is part of the contract (it feeds I4's
`mayBeIncomplete` neighbour-table hint) but the I1-locked schema has no
persisted column for it yet — `ingestion/pipeline.py` reads the field and
discards it until I4 adds the column via a new Alembic migration.

**Selecting an implementation.** Callers never import
`graphrev.adapters.ghidra.mock` or `.rest` directly — only
`graphrev/adapters/ghidra/__init__.py` may do so, per the `import-linter`
"Only adapters/*/base may be imported outside their own package" contract.
Use the factory instead:

```python
from graphrev.adapters.ghidra import create_adapter

adapter = create_adapter("mock", seed=1337)
```

`create_adapter("rest", ...)` raises `GhidraAdapterNotImplementedError` until
`RestGhidraAdapter` ships in Increment I12 (M1).

**`MockGhidraAdapter` (M0).** Given the same `seed`, every method returns
byte-identical output. It generates two binaries — `acme.exe` (~350
functions, to structurally host the required fan-out/fan-in shapes below)
and `libparse.dll` (~60 functions) — with:

- A shallow entry region (`main` → 12 callees) and four 4-deep parser chains.
- One function with 34 callees and one "dispatcher" with 300+ callees.
- At least three fan-in hubs with `fan_in > 50`, one with ≈291 callers
  (exercises D7's `CALLER_SUPPRESS_THRESHOLD`).
- A self-recursive function and a mutual-recursion pair.
- Several orphans (no callers, no callees).
- One function of each non-placeholder `kind` (`normal`, `import`, `thunk`,
  `external`); `placeholder` rows are never emitted directly by the adapter —
  they arise in `ingestion/pipeline.py` from unresolved cross-binary edges
  (see below).
- Unresolved edges from `acme.exe` into `libparse.dll` addresses that do not
  exist in either binary's own function list, with `callee_module` set —
  this is what a real adapter's `RawEdge.callee_module` is for.

**Placeholder materialisation (B17).** When `ingestion/pipeline.py` cannot
resolve a `RawEdge.callee_address` within the binary currently being
ingested, it creates a `kind='placeholder'` `functions` row under the
*same* `binary_id`, named `{module}!FUN_{address:08x}` (or bare
`FUN_{address:08x}` if `callee_module` is `None`). A later ingestion run of
the same binary that supplies a real `RawFunction` for that address upgrades
the row in place via the ordinary `(binary_id, address)` UPSERT — a real
adapter does not need to do anything special to support this; it only needs
to report `callee_module` accurately on `RawEdge` when it can.

## LLM adapter

Implement `graphrev.adapters.llm.base.LlmAdapter`:

```python
class LlmAdapter(Protocol):
    async def summarize(self, req: SummaryRequest) -> SummaryResult: ...
```

Map every provider error onto the `SummarizationError` taxonomy
(`TransientProviderError`, `RateLimitError`, `AuthError`,
`ContextTooLargeError`, `PermanentProviderError`) — the worker's
retry/backoff policy is driven entirely by these types.

Prompt content is explicitly out of scope for GraphRev's own architecture
(PRD `AS14`); `summarization/context.py` assembles the `SummaryRequest`, and
what a real adapter does with it (system prompt, model choice, truncation
strategy, prompt-injection fencing for untrusted binary content) is
adapter-owned.

### Implementations

- **`MockLlmAdapter`** (`adapters/llm/mock.py`, I7) — deterministic, seeded,
  latency/failure-simulating; the default.
- **`LiteLlmAdapter`** (`adapters/llm/litellm_adapter.py`, I13) — real
  summaries via `litellm.acompletion`. One adapter covers every provider
  litellm routes to (Anthropic / OpenAI / Ollama / vLLM / OpenRouter) via a
  provider-prefixed `GRAPHREV_LLM_MODEL` string; see README "Real LLM
  summaries (litellm)" for configuration. Its contract obligations:

  - Enforces a JSON response `{summary_short, summary_long, low_confidence}`
    validated with Pydantic — never regexes a prose blob. Unparseable output
    raises `PermanentProviderError` so garbage is never cached (C6).
  - Hard-clamps `summary_short` to one table row (C4) in the adapter — the
    DB column is what the UI trusts.
  - Truncates oversized `code_c` itself and reports `input_truncated`;
    raises `ContextTooLargeError` only if even the truncated form fails.
  - Fences untrusted content (decompiled C, strings, symbol names, notes) in
    delimited `<untrusted>` data blocks with an explicit data-not-
    instructions instruction (§5.1/§6.4).
  - Maps litellm's normalised exceptions onto the taxonomy:
    `RateLimitError`→`RateLimitError` (with `retry_after` when the provider
    supplies it), `AuthenticationError`→`AuthError`,
    `ContextWindowExceededError`→`ContextTooLargeError`,
    `APIConnectionError`/timeout→`TransientProviderError`.
  - `max_concurrency = settings.summary_concurrency` (stateless HTTP calls,
    AM1); `health()` is a one-token completion probe that never raises.

- **`OpenCodeAdapter`** (`adapters/llm/opencode_adapter.py`, I13) — an agent
  with ghidra-MCP access, driving a running `opencode serve` sidecar over
  plain `httpx` (no Node runtime dependency in the backend). One fresh
  session per function (no context bleed); `POST /session/:id/message`
  blocks until the agent answers, which is fine because the worker runs
  off-request. Sidecar configuration lives in `tools/opencode-ghidra/` (see
  its README). Its contract obligations:

  - `max_concurrency = 1` (AM1): the ghidra-MCP bridge drives one loaded
    program; parallel agents on one Ghidra instance are a correctness
    hazard, not just slow.
  - **Filename guard** (plan decision 5, deliberately loose): the agent's
    required JSON payload includes `program_filename` — the basename of the
    program currently loaded in Ghidra — verified post-hoc against
    `req.binary_name`. Mismatch raises `GhidraProgramMismatchError`, which
    the worker persists as `summary_error_code = GHIDRA_PROGRAM_MISMATCH`
    with nothing cached: a wrong summary is unrecoverable because
    `summary_*` is ingestion-immutable (A3).
  - Enforces a JSON response `{summary_short, summary_long,
    low_confidence, program_filename}` validated with Pydantic; unparseable
    output raises `PermanentProviderError` (C6). Hard-clamps
    `summary_short` (C4) and truncates oversized `code_c` like the litellm
    adapter.
  - Bounded agent loop: `agent_max_tool_calls` (stated in the prompt and the
    agent definition) and `agent_timeout_seconds` via `asyncio.timeout` —
    an unbounded agent on a 1-wide queue is a permanent stall.
  - Maps transport failures onto the taxonomy: connect/timeout→
    `TransientProviderError`, 401/403→`AuthError`, 429→`RateLimitError`,
    5xx→`TransientProviderError`, other 4xx→`PermanentProviderError`.
  - `health()` probes `GET /global/health` + `GET /mcp` (AM5) and never
    raises; surfaced as `llmHealth` on `GET /health`.
