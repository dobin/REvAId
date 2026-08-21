# ADR 0002 — Alembic from commit one (deviation from PRD §5.2)

## Status

Accepted (TAD §1.3, locked for Milestone 1 / TAD Increment I1).

## Context

PRD §5.2 lists "migrations, deployment packaging, containerization" as
explicitly **out of scope** for v0 (the UI-validation milestone). Taken
literally, that would mean the M0 database is created by
`Base.metadata.create_all()` with no migration history at all.

The TAD (§1.3) argues against this: the M0 → M1 transition adds real-Ghidra
columns (real `fan_in`, incremental single-function ingest, etc.) to a
database that, by M1, contains an analyst's renames and notes — exactly the
"single worst failure this product can have" per PRD §5.1 if that transition
requires dropping and recreating the schema.

## Decision

- Alembic is used from the very first commit. `migrations/versions/0001_initial.py`
  is the **only** way a GraphRev database is created — there is no
  `metadata.create_all()` code path anywhere, including in tests (which run
  `alembic upgrade head` against a temp-file SQLite DB via
  `tests/conftest.py`).
- `B12` ("migrations are versioned") is a *Should* in the PRD; this decision
  promotes it to a *de facto* Must for M0 as a documented, deliberate
  deviation from PRD §5.2.
- `F5` (containerization) remains genuinely out of scope for M0/M1 — this
  ADR does **not** extend to Docker/packaging.

## Consequences

- `just migrate` (`alembic upgrade head`) is a required step before `just
  dev` or `just test` will work against a fresh clone; `main.py`'s lifespan
  fails loudly with an actionable message if the DB has no
  `alembic_version` row, rather than silently creating tables.
- The I1 exit test asserts that `alembic revision --autogenerate` against
  `db/models.py` produces an **empty diff** against `0001_initial.py` — this
  is the guard that keeps the model and the migration from drifting apart.
