set shell := ["bash", "-cu"]
set dotenv-load := true
set dotenv-path := "backend/.env"

default:
    @just --list

# --- setup ---------------------------------------------------------------

setup: setup-noui
    cd frontend && npm install

setup-noui:
    cd backend && uv sync

# --- dev -------------------------------------------------------------------

ui:
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' EXIT
    just _analysis &
    just _viewer &
    just _web &
    wait

# Build the SPA and serve it alongside the split backends without reloads.
# Pass Caddy's public hostname so Vite accepts its forwarded Host header.
prod domain="":
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' EXIT
    export GRAPHREV_WEB_DOMAIN="{{ domain }}"
    just _web-build
    just _analysis-prod &
    just _viewer-prod &
    just _web-prod &
    wait

# Build only when the saved bundle is missing or a frontend input changed.
_web-build:
    #!/usr/bin/env bash
    set -euo pipefail
    output="frontend/dist/index.html"
    if [[ ! -f "$output" ]] || \
       find frontend/src \
            frontend/index.html \
            frontend/package.json \
            frontend/package-lock.json \
            frontend/vite.config.ts \
            frontend/tsconfig.json \
            frontend/tsconfig.app.json \
            frontend/tsconfig.node.json \
            frontend/postcss.config.js \
            frontend/tailwind.config.ts \
            -type f -newer "$output" -print -quit | grep -q .; then
        cd frontend
        npm run build
    else
        echo "Frontend bundle is up to date; reusing frontend/dist"
    fi

# Rebuild the SPA even when the saved bundle appears current.
_web-build-force:
    cd frontend && npm run build

_analysis:
    cd backend && uv run uvicorn revaid.main:app --reload \
        --host "${GRAPHREV_ANALYSIS_HOST:-${GRAPHREV_HOST:-127.0.0.1}}" \
        --port "${GRAPHREV_ANALYSIS_PORT:-${GRAPHREV_PORT:-8000}}"

_analysis-prod:
    cd backend && uv run uvicorn revaid.main:app --host "${GRAPHREV_ANALYSIS_HOST:-127.0.0.1}" --port "${GRAPHREV_ANALYSIS_PORT:-8000}" --workers 1

_viewer:
    cd backend && uv run uvicorn revaid_ui.main:app --reload \
        --host "${GRAPHREV_VIEWER_HOST:-${GRAPHREV_HOST:-127.0.0.1}}" \
        --port "${GRAPHREV_VIEWER_PORT:-8002}"

_viewer-prod:
    cd backend && uv run uvicorn revaid_ui.main:app --host "${GRAPHREV_VIEWER_HOST:-127.0.0.1}" --port "${GRAPHREV_VIEWER_PORT:-8002}" --workers 1

_web-prod:
    cd frontend && npm run preview -- \
        --host "${GRAPHREV_WEB_HOST:-127.0.0.1}" \
        --port "${GRAPHREV_WEB_PORT:-4173}"

mcp:
    cd backend && GRAPHREV_MCP_HOST="${GRAPHREV_MCP_HOST:-${GRAPHREV_HOST:-127.0.0.1}}" uv run graphrev-mcp

viewer-stats:
    cd backend && uv run revaid-ui-db

_web:
    cd frontend && npm run dev -- \
        --host "${GRAPHREV_WEB_HOST:-${GRAPHREV_HOST:-127.0.0.1}}" \
        --port "${GRAPHREV_WEB_PORT:-5173}"

ingest *args:
    cd backend && uv run graphrev ingest {{ args }}

# --- database --------------------------------------------------------------

migrate:
    cd backend && uv run alembic upgrade head
    cd backend && uv run alembic -c viewer_alembic.ini upgrade head

migrate-analysis:
    cd backend && uv run alembic upgrade head

migrate-viewer:
    cd backend && uv run alembic -c viewer_alembic.ini upgrade head

db-reset-analysis:
    rm -f backend/graphrev.db backend/graphrev.db-wal backend/graphrev.db-shm
    just migrate-analysis

db-reset-viewer:
    rm -f backend/graphrev-viewer.db backend/graphrev-viewer.db-wal backend/graphrev-viewer.db-shm
    just migrate-viewer

revision name:
    cd backend && uv run alembic revision --autogenerate -m "{{ name }}"

db-reset:
    rm -f backend/graphrev.db backend/graphrev.db-wal backend/graphrev.db-shm
    rm -f backend/graphrev-viewer.db backend/graphrev-viewer.db-wal backend/graphrev-viewer.db-shm
    just migrate

# --- quality gates -----------------------------------------------------------

test: test-py test-ts

# Full backend suite INCLUDING `slow` (real-CLI-subprocess) tests. This is the
# CI/quality-gate entrypoint. A bare `uv run pytest` (the fast editor loop)
# deselects `slow` via `addopts = -m 'not slow'` in pyproject.toml.
test-py:
    cd backend && uv run pytest -m "slow or not slow"

# Fast local loop: everything except the `slow` CLI-subprocess tests.
test-py-fast:
    cd backend && uv run pytest

test-ts:
    cd frontend && npm run test

lint: lint-py lint-ts magic-numbers

lint-py:
    cd backend && uv run ruff check .
    cd backend && uv run ruff format --check .
    cd backend && uv run mypy src
    cd backend && uv run lint-imports

lint-ts:
    cd frontend && npm run lint
    cd frontend && npm run typecheck

fmt:
    cd backend && uv run ruff format .
    cd backend && uv run ruff check --fix .
    cd frontend && npm run format

typecheck:
    cd backend && uv run mypy src
    cd frontend && npm run typecheck

magic-numbers:
    ./scripts/check-magic-numbers.sh

gen-types:
    cd frontend && npm run gen-types
