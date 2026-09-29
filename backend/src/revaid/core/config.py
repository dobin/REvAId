"""Application configuration.

The settings schema lives in :mod:`revaid_contracts.config` (shared with the
viewer). This module keeps the analysis-side import path stable.

Every numeric threshold that the PRD or TAD names must live in that schema and
nowhere else. ``GET /api/v1/config`` (E1d) is the *only* projection of it to the
frontend; components must never hard-code such a value (enforced by
``scripts/check-magic-numbers.sh``).
"""

from __future__ import annotations

from functools import lru_cache

from revaid_contracts.config import NODE_COLOR_PALETTE, GhidraAdapterName, LlmAdapterName
from revaid_contracts.config import Settings as SharedSettings


class Settings(SharedSettings):
    """Analysis process settings; fields and validators are inherited unchanged."""


@lru_cache
def get_settings() -> Settings:
    """Process-wide cached Settings instance.

    Cached so every module sees the same values within a process; tests should
    call ``get_settings.cache_clear()`` after mutating environment variables.
    """
    return Settings()


__all__ = [
    "NODE_COLOR_PALETTE",
    "GhidraAdapterName",
    "LlmAdapterName",
    "Settings",
    "get_settings",
]
