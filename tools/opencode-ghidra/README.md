# GraphRev opencode–Ghidra sidecar

This directory is the configuration for the **opencode agent backend** of
GraphRev's I13 "option B" LLM adapter (`OpenCodeAdapter`,
`backend/src/graphrev/adapters/llm/opencode_adapter.py`).

`opencode serve` **is** the sidecar (plan decision 4): a headless HTTP server
the backend talks to with plain `httpx` — no custom bridge web service, no
Node runtime dependency in the backend. The agent it serves (`graphrev-re`)
has read-only access to a running Ghidra instance through a ghidra-MCP
bridge, so it can drive Ghidra itself rather than summarising from the
decompiled C GraphRev already has.

## Files

| File | Purpose |
| ---- | ------- |
| `opencode.json` | The `mcp` block wiring the ghidra-MCP bridge. |
| `.opencode/agent/graphrev-re.md` | The `graphrev-re` agent: read-only permission set, ghidra MCP tools, JSON-only output contract (incl. the `program_filename` guard field). |

## Running it

1. Start Ghidra with the target binary loaded and the ghidra-MCP bridge
   plugin listening (see the bridge's own docs for its port).
2. From this directory:

   ```bash
   cd tools/opencode-ghidra
   OPENCODE_SERVER_PASSWORD=... opencode serve
   ```

   The server listens on `127.0.0.1:4096` by default; its OpenAPI spec is at
   `http://127.0.0.1:4096/doc`.

3. Point the GraphRev backend at it (`.env` in `backend/`):

   ```dotenv
   GRAPHREV_LLM_ADAPTER=opencode
   GRAPHREV_OPENCODE_URL=http://127.0.0.1:4096
   GRAPHREV_OPENCODE_AGENT=graphrev-re
   GRAPHREV_OPENCODE_PASSWORD=...          # same as OPENCODE_SERVER_PASSWORD
   GRAPHREV_AGENT_MAX_TOOL_CALLS=40
   GRAPHREV_AGENT_TIMEOUT_SECONDS=300
   ```

4. Verify wiring via `GET /api/v1/health` — `llmHealth.reachable` is false
   until both `opencode serve` and the ghidra-MCP connection are up (AM5:
   "no summaries because misconfigured" must be distinguishable from "no
   summaries yet").

## The filename guard

Before the backend accepts any summary from the agent, the agent's JSON
payload must report `program_filename` — the basename of the program
currently loaded in Ghidra — and it must match the requested binary's
filename (deliberately loose: filename only, no hashing; plan decision 5).
On mismatch the summary is discarded with error code
`GHIDRA_PROGRAM_MISMATCH` and **nothing is written to `summary_*`**: a wrong
summary is unrecoverable because `summary_*` columns are ingestion-immutable
by design (A3).

## Concurrency

The adapter declares `max_concurrency = 1` (AM1): the ghidra-MCP bridge
drives one loaded program, so parallel agents on one Ghidra instance are a
correctness hazard, not just slow. The worker pool honours this via
`min(settings.summary_concurrency, adapter.max_concurrency)`.
