"""Opaque identifier generation for public mode (ADR 0006).

In public mode a view id is also its only access credential (a capability):
whoever holds it can read and patch the view, so it must be unguessable.
Ordinary autoincrement ids are enumerable; the random id here is not.

The upper bound is ``2**53 - 1`` — the largest integer JavaScript can
represent exactly — because `ViewId` travels over the wire as a JSON number
and the frontend keeps view ids as `number`, not `string`.
"""

from __future__ import annotations

import secrets
import string

#: 2**53 - 1 — largest exactly-representable JS integer (Number.MAX_SAFE_INTEGER).
_VIEW_ID_MAX = 2**53 - 1

_PUBLIC_BINARY_PREFIX_LENGTH = 4


def public_binary_name(name: str) -> str:
    """Prefix an uploaded binary name with four random lowercase letters."""
    prefix = "".join(
        secrets.choice(string.ascii_lowercase) for _ in range(_PUBLIC_BINARY_PREFIX_LENGTH)
    )
    return f"{prefix}_{name}"


def random_view_id() -> int:
    """A uniformly random integer in ``[1, 2**53 - 1]``.

    ``secrets.randbelow`` is cryptographically secure, so ids are not merely
    "hard to guess" but genuinely unguessable, matching the capability model.
    """
    return secrets.randbelow(_VIEW_ID_MAX) + 1
