"""Injectable clock.

All timestamps in the DB are ISO-8601 UTC strings (TAD §3.3 design note). Every
write path must go through :func:`utc_now_iso` rather than calling
``datetime.now`` directly, so tests can freeze time with ``freezegun``.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Current time as a timezone-aware UTC ``datetime``."""
    return datetime.now(UTC)


def utc_now_iso() -> str:
    """Current time as an ISO-8601 UTC string, e.g. ``2026-08-21T10:14:02Z``."""
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
