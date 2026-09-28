"""Viewer-specific configuration, retaining the established GRAPHREV_ names."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from revaid_contracts.config import Settings as SharedSettings


class Settings(SharedSettings):
    """Viewer configuration isolated from analysis implementation modules."""

    model_config = SettingsConfigDict(
        env_prefix="GRAPHREV_",
        env_file=SharedSettings.model_config["env_file"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # UI state is stored separately from analysis records.
    viewer_db_path: str = Field(default="./graphrev-viewer.db")


@lru_cache
def get_settings() -> Settings:
    return Settings()
