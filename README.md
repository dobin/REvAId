# Revealm - reverse + realm, mapping an unknown world

**I cant code but i must reverse**

Revealm is a semantic function graph explorer for binary reverse
engineering: it renders a binary's call graph as interactive cards, lazily
summarizes functions with an LLM, and lets an analyst annotate what they
find. 

This is 100% vibe coded. Claude 5. See `IDEA.md`, `PRD.md`, `TAD.md`.

Ghidra and LLM integrations ship as deterministic **mocks** in M0/M1 of this
milestone — see `docs/adapters.md` for the real-adapter contract.

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) (Python 3.12 package/env manager)
- Node.js 22+ and npm
- [`just`](https://github.com/casey/just) (task runner)

## Quickstart

```sh
just setup    # uv sync (backend) + npm install (frontend)
just migrate  # alembic upgrade head — the ONLY way the DB schema is created
just dev      # runs the API (uvicorn, :8000) and the SPA (Vite, :5173) together
```

Then open http://127.0.0.1:5173 — you should see a small panel showing live
`/health` and `/config` data, proving the frontend, backend, and database are
wired together end to end.

## Everyday commands

| Command | What it does |
| --- | --- |
| `just dev` | Run API + web concurrently (F3) |
| `just api` / `just web` | Run just one side |
| `just migrate` | Apply pending Alembic migrations |
| `just revision name="add x"` | Autogenerate a new migration from `db/models.py` |
| `just db-reset` | Delete the local SQLite file and re-migrate from scratch |
| `just test` | Run backend (pytest) and frontend (vitest) test suites |
| `just lint` | ruff, mypy --strict, import-linter, eslint, tsc, magic-number guard |
| `just fmt` | Auto-format both backend and frontend |
| `just gen-types` | Regenerate `frontend/src/api/generated.ts` from the live OpenAPI schema |

## Configuration

All tunable thresholds (`TABLE_ROW_CAP`, `CALLER_SUPPRESS_THRESHOLD`,
`UTILITY_FANIN_THRESHOLD`, `FAN_OUT_ALL_HARD_CAP`, `NODE_COUNT_SOFT_WARNING`,
plus adapter selection and everything else) live in
`backend/src/graphrev/core/config.py` and are set via environment variables
(prefix `GRAPHREV_`) or a `.env` file — see `.env.example`. They are exposed
to the frontend as a single payload from `GET /api/v1/config`; no component
may hard-code a threshold (enforced by `scripts/check-magic-numbers.sh`,
which also runs in CI).

`MockLlmAdapter`'s simulated latency (1-8s per TAD §6.3) is **off by
default** (`GRAPHREV_MOCK_LLM_SIMULATE_LATENCY=false`) so `just test` and
everyday `just dev` get fast, near-instant mock summaries. Set it to `true`
(plus optionally `GRAPHREV_MOCK_LLM_MIN_LATENCY_SECONDS` /
`_MAX_LATENCY_SECONDS`) when you want to manually exercise the
pending/shimmer/queue-depth UI under realistic timing. A small
`GRAPHREV_MOCK_LLM_FAILURE_RATE` (default `0.05`) stays on even with latency
off, so the summary error+retry state is reachable in a normal demo; set it
to `0` to disable.

### Real LLM summaries (litellm)

Set `GRAPHREV_LLM_ADAPTER=litellm` to summarise with a real model instead of
the mock. The adapter is backed by [litellm](https://docs.litellm.ai/), so
one configuration covers every provider it routes to — Anthropic, OpenAI,
Ollama, vLLM, OpenRouter — which is the point: retuning the model is a
config change, not a code change.

| Variable | Meaning |
| --- | --- |
| `GRAPHREV_LLM_ADAPTER=litellm` | Select the litellm adapter |
| `GRAPHREV_LLM_MODEL` | litellm router string, e.g. `anthropic/claude-sonnet-4-5`, `openai/gpt-4o`, `ollama/llama3` |
| `GRAPHREV_LLM_API_KEY` | Provider API key (put it in `.env`, not the shell) |
| `GRAPHREV_LLM_API_BASE` | Base URL for self-hosted/proxied endpoints (Ollama, vLLM, an LLM gateway); leave unset for hosted providers |
| `GRAPHREV_SUMMARY_REQUEST_TIMEOUT_SECONDS` | Per-request bound (default `120`) so a hung provider cannot wedge a worker |
| `GRAPHREV_LLM_TEMPERATURE` | Sampling temperature (default `0`). Summarising is structured extraction, not creative writing — a higher value makes models wrap their JSON in markdown fences or prose |
| `GRAPHREV_LLM_JSON_ATTEMPTS` | How many times to ask before giving up on parseable JSON (default `3`). Malformed output is flaky rather than deterministic, so a retry avoids spuriously marking a function errored |

Examples:

```sh
# Anthropic (key from https://console.anthropic.com/)
GRAPHREV_LLM_ADAPTER=litellm
GRAPHREV_LLM_MODEL=anthropic/claude-sonnet-4-5
GRAPHREV_LLM_API_KEY=sk-ant-...

# Local Ollama — no key needed
GRAPHREV_LLM_ADAPTER=litellm
GRAPHREV_LLM_MODEL=ollama/llama3
GRAPHREV_LLM_API_BASE=http://127.0.0.1:11434
```

The adapter enforces a JSON response shape (`summary_short` / `summary_long`
/ `low_confidence`), clamps `summary_short` to one table row, fences
untrusted binary content (decompiled code, strings, symbol names) behind
delimited data blocks, and maps provider errors (rate limit, auth, context
overflow, connection) onto the internal error taxonomy that drives retry and
queue-pause behaviour. Which adapter produced each summary is recorded in
`functions.summary_adapter` and exposed on the API, but not surfaced in the
UI yet.

## Adding a migration

The database schema is created **exclusively** through Alembic — there is no
`create_all()` path, even in tests (see `docs/adr/0002-alembic-in-v0.md`).
After changing `backend/src/Revealm/db/models.py`:

```sh
just revision name="describe your change"
just migrate
```

Then verify there is no drift between the models and the migration:

```sh
cd backend && uv run pytest tests/db/test_schema_snapshot.py
```

## Project layout

See TAD §5 for the full directory structure. In short: `backend/` is a
FastAPI + SQLAlchemy 2.0 (async) + Alembic service managed by `uv`;
`frontend/` is a React 19 + TypeScript (strict) + Vite 6 SPA; `docs/adr/`
records architectural decisions and deliberate deviations from the PRD.
