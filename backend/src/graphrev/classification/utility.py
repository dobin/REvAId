"""The single swappable utility-classification predicate (D34a, AS28).

`fan_in > UTILITY_FANIN_THRESHOLD` — chosen because it needs no new data
source, works on stripped binaries, and reuses the caller-count machinery D7
already requires (PRD §7.2 rationale).

This formula must stay **textually identical** to the raw-SQL recompute in
`graphrev.db.startup.recompute_utility_if_threshold_changed`
(``UPDATE functions SET is_utility = (fan_in > :threshold)``) — that startup
hook and `ingestion/pipeline.py`'s ingest-time computation must never
disagree about what "utility" means. If a sharper classifier (leaf+fan-in,
Ghidra `kind`, name list — TAD I14/TQ5) replaces this predicate, both call
sites must be updated together.
"""

from __future__ import annotations


def is_utility(fan_in: int, threshold: int) -> bool:
    """Whether a function with `fan_in` distinct callers is a utility function.

    `is_utility` is demote-not-hide and never destructive: `utility_override`
    (D36) always wins over this predicate's output, and the root card is never
    demoted regardless of this function's result (enforced by callers, not
    here — this predicate is intentionally the *only* thing that changes if
    the classification strategy changes).
    """
    return fan_in > threshold
