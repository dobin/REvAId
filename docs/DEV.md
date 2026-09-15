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



## Configuration

All tunable thresholds (`TABLE_ROW_CAP`, `CALLER_SUPPRESS_THRESHOLD`,
`UTILITY_FANIN_THRESHOLD`, `FAN_OUT_ALL_HARD_CAP`, `NODE_COUNT_SOFT_WARNING`,
plus adapter selection and everything else) live in
`backend/src/graphrev/core/config.py` and are set via environment variables
(prefix `GRAPHREV_`) or a `.env` file at `backend/.env` — see
`backend/.env.example`. They are exposed
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



### Public demo mode

Set `GRAPHREV_PUBLIC_MODE=true` when exposing an instance to anonymous
visitors (see `docs/adr/0006-public-mode-anonymous-views.md`). Every browser
then gets its own private views — tracked client-side in `localStorage` —
instead of everyone landing on the binary's shared default view, so
anonymous visitors cannot clobber each other's canvas (or yours).

In public mode the shared view-listing endpoint is closed and view ids are
cryptographically random, so a visitor cannot enumerate other people's
views. The view picker lists only that browser's own views, and the shared
`last-view` pointer (B16) is not written.

Off by default: a private instance keeps the single-user behaviour where
every browser shares the binary's views. Note that public mode is "secure
enough for a demo", not authorization — the view id is the credential, so
someone who learns it (a shared link, a screenshot) can still read/modify
that view. Hardening against hostile clients needs real auth.

Caveat: enable public mode on a fresh DB (or re-ingest), since random ids
are only assigned at view-creation time — flipping it on a DB that already
has sequential view ids leaves those old ids guessable.

#### Curating the initial canvas

`functions.is_featured` is an operator-owned marker for functions that should
appear in every **new** view. This is especially useful in public mode: a new
anonymous `My view` starts with the curated functions instead of an empty
canvas. Private-mode view creation uses the same template. Featured functions
become independent root nodes and the normal ELK layout arranges them; the
lowest-address featured function anchors the initial camera.

The template is copied only when a view is created. Changing the marker does
not mutate existing views, and removing a featured node from one view remains
durable. Re-ingestion also preserves the marker. With the app stopped, mark
functions using SQLite (adjust the binary name and addresses):

```sql
BEGIN IMMEDIATE;
UPDATE functions
SET is_featured = 1
WHERE binary_id = (
	SELECT id FROM binaries WHERE name = 'sample.exe' AND version = ''
)
AND address IN (4198400, 4198448);
COMMIT;
```

Addresses are stored as integers; SQLite accepts hexadecimal integer literals
such as `0x401000` as well. Newly created views now receive those functions.
To backfill missing featured nodes into an already-existing `Default` view
without overwriting its current nodes, positions, or colors:

```sql
BEGIN IMMEDIATE;
INSERT OR IGNORE INTO view_nodes (
	view_id, function_id, visible, collapsed, color, pos_x, pos_y, pinned,
	origin_function_id, origin_kind, origin_implied, created_at, updated_at
)
SELECT
	v.id, f.id, 1, 0, NULL, 0.0, 0.0, 0,
	NULL, 'root', 0,
	strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
	strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
FROM views AS v
JOIN binaries AS b ON b.id = v.binary_id
JOIN functions AS f ON f.binary_id = b.id AND f.is_featured = 1
WHERE b.name = 'sample.exe' AND b.version = '' AND v.name = 'Default';

UPDATE views
SET root_function_id = (
		SELECT f.id
		FROM functions AS f
		WHERE f.binary_id = views.binary_id AND f.is_featured = 1
		ORDER BY f.address, f.id
		LIMIT 1
	),
	updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
WHERE name = 'Default'
  AND binary_id = (
	  SELECT id FROM binaries WHERE name = 'sample.exe' AND version = ''
  )
  AND EXISTS (
	  SELECT 1 FROM functions AS f
	  WHERE f.binary_id = views.binary_id AND f.is_featured = 1
  );
COMMIT;
```

If no functions are featured, the existing empty-view entry-point fallback is
unchanged.


### LLM 

| `GRAPHREV_SUMMARY_REQUEST_TIMEOUT_SECONDS` | Per-request bound (default `120`) so a hung provider cannot wedge a worker |
| `GRAPHREV_LLM_TEMPERATURE` | Sampling temperature (default `0`). Summarising is structured extraction, not creative writing — a higher value makes models wrap their JSON in markdown fences or prose |
| `GRAPHREV_LLM_JSON_ATTEMPTS` | How many times to ask before giving up on parseable JSON (default `3`). Malformed output is flaky rather than deterministic, so a retry avoids spuriously marking a function errored |


The adapter enforces a JSON response shape (`summary_short` / `summary_long`
/ `low_confidence`), clamps `summary_short` to one table row, fences
untrusted binary content (decompiled code, strings, symbol names) behind
delimited data blocks, and maps provider errors (rate limit, auth, context
overflow, connection) onto the internal error taxonomy that drives retry and
queue-pause behaviour. Which adapter produced each summary is recorded in
`functions.summary_adapter` and exposed on the API, but not surfaced in the
UI yet.

