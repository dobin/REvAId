# Dev Notes

## Project layout

See TAD §5 for the full directory structure. In short: `backend/` is a
FastAPI + SQLAlchemy 2.0 (async) + Alembic service managed by `uv`;
`frontend/` is a React 19 + TypeScript (strict) + Vite 6 SPA; `docs/adr/`
records architectural decisions and deliberate deviations from the PRD.


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