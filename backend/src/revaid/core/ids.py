"""Public-mode identifier helpers (ADR 0006)."""

from __future__ import annotations

import secrets
import string

_PUBLIC_BINARY_PREFIX_LENGTH = 4


def public_binary_name(name: str) -> str:
    """Prefix an uploaded binary name with four random lowercase letters."""
    prefix = "".join(
        secrets.choice(string.ascii_lowercase) for _ in range(_PUBLIC_BINARY_PREFIX_LENGTH)
    )
    return f"{prefix}_{name}"
