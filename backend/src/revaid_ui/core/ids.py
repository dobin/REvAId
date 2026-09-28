"""Viewer-specific opaque identifiers."""

from __future__ import annotations

import secrets

_VIEW_ID_MAX = 2**53 - 1


def random_view_id() -> int:
    """Generate a positive 63-bit capability identifier for an anonymous view."""
    return secrets.randbelow(_VIEW_ID_MAX) + 1
