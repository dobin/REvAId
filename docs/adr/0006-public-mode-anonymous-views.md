# ADR 0006 — Public mode: anonymous per-browser views via localStorage

## Status

Accepted (2026-09-01).

## Context

GraphRev is a single-user, locally-run tool by design (AS1, B18: no auth,
no concurrency control, last-write-wins). But it is also demoed publicly:
an instance exposed to anonymous visitors puts every browser onto the same
binary's shared views, so two visitors (or a visitor and the owner) editing
the same view silently overwrite each other's canvas — positions, colors,
visibility, collapse state.

The PRD's own answer to multi-user is B15 ("views are the seam that makes
this cheap later"), and the server side already has everything needed:
`views`/`view_nodes` are per-view rows with full CRUD (`POST
/binaries/{id}/views`, `GET /views/{id}`, …). The only *shared* pointer is
`binaries.last_view_id` (B16) plus the client's "default to the first view"
resolution — that is the entire collision surface.

Two alternatives were considered:

1. **Client-owned canvas + explicit "save view" snapshots.** The canvas
   document becomes client-authoritative (Zustand + localStorage), and the
   server is demoted to a snapshot store behind an explicit save action
   that can be disabled in public. Rejected for now: it reworks the
   persistence model (`E2`'s `view_id`/`on_canvas` coupling, the mutation
   layer, view lifecycle) — a large change for a problem that is, today,
   only about anonymous demos.
2. **Anonymous per-browser view ids (this ADR).** Keep server-authoritative
   views untouched; move the "which view is mine" pointer from the server
   (`last_view_id`) into the browser (`localStorage`). Each browser gets
   its own private views; the server never learns who owns what.

## Decision

A `GRAPHREV_PUBLIC_MODE` flag (default `false`) on `Settings`, surfaced to
the frontend as `publicMode` on `GET /config` (E1d's single-payload
contract — no second config channel).

When `publicMode` is **true**:

**Backend (enumeration is closed, ids become capabilities).**

- `GET /binaries/{id}/views` and `POST /binaries/{id}/last-view` return
  `403 PUBLIC_MODE_FORBIDDEN` — the shared view listing and last-used
  pointer would otherwise enumerate every browser's view id.
- View creation (`POST /binaries/{id}/views`) and duplication assign a
  cryptographically random integer id in `[1, 2^53-1]` (via
  `secrets.randbelow`, so the id stays a JS `number`). The seeded default
  view also gets a random id when ingested under public mode. The id is now
  a *capability*: by-id endpoints (`GET/PATCH/DELETE /views/{id}`) stay open,
  so holding the id is what grants access — it is unguessable and never
  disclosed by a listing.
- `GET /binaries` redacts `lastViewId` to `null` so the owner's last-used
  view cannot leak through the binary listing.

**Frontend (no listing call at all).**

- Owned views live in `localStorage` as `{ id, name }[]` per binary — the
  name is stored alongside the id so the picker renders without a `GET
  /views` round trip.
- The workspace resolves its view from that list (creating a fresh view on
  first visit); the `useViewsQuery` listing query is disabled in public mode.
- The picker lists only owned views and skips the `last-view` write.

When `publicMode` is **false** (private instance), nothing changes: the
workspace defaults to the binary's first view, the picker lists all views,
view switches persist `last_view_id` (B16 intact), and view ids remain
sequential autoincrement integers.

This is "secure enough" for a public demo — it stops casual enumeration and
accidental clobbering — but it is **not authorization**: someone who
learns a view id (a shared link, a screenshot, logs) can still read and
modify that view, and the id cannot be revoked without changing every
reference to it. A public instance that must resist hostile clients needs
real auth (B15's future seam), not this flag.

## Consequences

- Anonymous visitors stop clobbering each other's canvas and can no longer
  enumerate every view (and the owner's `lastViewId`) by calling the API.
- Summaries, analyst names, and notes remain function-scoped and shared
  across views (AS2) — one visitor's summarisation work still benefits
  everyone, which is a feature in a demo. This also means view-id
  randomness protects the *canvas layout* only; notes/renames on a shared
  function are still shared and writable.
- Views created by anonymous browsers accumulate in the DB. That is the
  same cost as any view CRUD usage; a public instance can prune old
  anonymous views with a periodic `DELETE /views/{id}` sweep if it ever
  matters (the rows are identifiable only by convention — nothing marks
  them, which is acceptable because the server treats all views alike).
- `binaries.last_view_id` becomes a private-instance-only convenience in
  public mode; the column and endpoint stay (B16 unchanged for private use).
- **Residual caveat:** flipping `PUBLIC_MODE` on a *populated* DB leaves
  pre-existing low (sequential) ids guessable, because random ids are only
  assigned at creation time. Enable public mode on a fresh DB, or re-ingest
  so the default view is (re)created with a random id.
- If the client-owned snapshot model (alternative 1) is ever wanted, this
  ADR's localStorage ownership module is the natural place to hang it —
  "my views" becomes "my snapshots" without touching the server contract.
