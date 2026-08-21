"""Summary input hashing (C10 stale detection).

``functions.summary_input_hash`` lets the worker detect that a cached summary no
longer reflects the current inputs (code, name, notes, callee summaries) without
storing the inputs themselves. Written now (the column exists from I1); the
worker that consumes it arrives in I7/I9.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def summary_input_hash(**inputs: Any) -> str:
    """Stable SHA-256 over the summarization inputs.

    Keys are sorted so field order never changes the hash. Values must be
    JSON-serialisable (str, int, bool, None, list/dict thereof).
    """
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
