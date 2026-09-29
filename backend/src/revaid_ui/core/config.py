"""Viewer configuration, retaining the established GRAPHREV_ names."""

from __future__ import annotations

from functools import lru_cache

from revaid_contracts.config import Settings as SharedSettings


class Settings(SharedSettings):
    """Viewer settings; fields (including ``viewer_db_path``) are inherited unchanged."""


@lru_cache
def get_settings() -> Settings:
    return Settings()
