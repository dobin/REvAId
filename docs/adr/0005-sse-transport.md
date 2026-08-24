# ADR 0005 — SSE transport: hand-rolled generator, not `sse-starlette`

## Status

Accepted (I8, 2026-08-24).

## Context

TQ2 (TAD §7, open question) asks whether `GET /events` (endpoint 22, E5)
should be implemented with the `sse-starlette` package or a hand-rolled
`StreamingResponse` generator. The TAD's own dependency table (§5) already
flags `sse-starlette` as *optional*: "thin; a hand-rolled generator is
acceptable — one dependency, one decision, documented in an ADR."

What `GET /events` actually needs, per TAD §2.7 / §4.2 #22:

- `Content-Type: text/event-stream`, `Cache-Control: no-cache`,
  `X-Accel-Buffering: no` response headers.
- `id:`/`event:`/`data:` frames with a monotonic `id:` per event.
- A `: keepalive` comment every `sse_keepalive_seconds` (15s default) to
  defeat proxy idle timeouts.
- Per-subscriber backpressure: a bounded queue: 256 default
  (`sse_subscriber_queue_size`), closing with a `reconcile` event on overflow
  rather than silently dropping events.
- Clean unsubscribe on disconnect (`asyncio.CancelledError` when Starlette
  tears the response down).

All five of these are a few dozen lines of plain `asyncio` + string
formatting (`events/bus.py`, `events/sse.py`) — no framing edge cases,
retry-header negotiation, or multi-transport fallback that would justify a
dependency. `sse-starlette` mainly buys automatic `Last-Event-ID` replay and
a `ping` helper; M0 explicitly does not implement replay (`§2.7`: "M0 does
not replay"), so that feature would be dead weight.

## Decision

Hand-rolled: `events/bus.py::InProcessEventBus` (pub/sub + bounded
per-subscriber queues) and `events/sse.py::sse_event_stream` (the async
generator, plain string frames) feeding a Starlette `StreamingResponse` in
`api/routers/events.py`. No new dependency added to `pyproject.toml`.

## Consequences

- One fewer third-party dependency to track for CVEs/breaking changes.
- If a future increment needs replay-on-reconnect (an *additive* change per
  §2.7's own note about monotonic `id:`s), it can be built directly on
  `InProcessEventBus` without migrating transport libraries.
- If SSE needs ever grow past what's listed above (e.g. per-client filtering,
  multi-process fan-out), revisit this decision — `sse-starlette` or a real
  message broker both remain viable escape hatches.
