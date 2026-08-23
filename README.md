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
`backend/src/Revealm/core/config.py` and are set via environment variables
(prefix `Revealm_`) or a `.env` file — see `.env.example`. They are exposed
to the frontend as a single payload from `GET /api/v1/config`; no component
may hard-code a threshold (enforced by `scripts/check-magic-numbers.sh`,
which also runs in CI).

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
