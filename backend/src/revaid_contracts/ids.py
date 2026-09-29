"""Opaque identifier generation for public mode (ADR 0006).

In public mode a view id is also its only access credential (a capability):
whoever holds it can read and patch the view, so it must be unguessable.

The upper bound is ``2**53 - 1`` — the largest integer JavaScript can represent
exactly — because ``ViewId`` travels over the wire as a JSON number.
"""

from __future__ import annotations

import secrets

__all__ = ["random_view_id"]

#: 2**53 - 1 — largest exactly-representable JS integer (Number.MAX_SAFE_INTEGER).
_VIEW_ID_MAX = 2**53 - 1


def random_view_id() -> int:
    """A uniformly random integer in ``[1, 2**53 - 1]`` (cryptographically secure)."""
    return secrets.randbelow(_VIEW_ID_MAX) + 1
