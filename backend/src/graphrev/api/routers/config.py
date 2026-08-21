"""``GET /config`` (E1d)."""

from __future__ import annotations

from fastapi import APIRouter

from graphrev.api.deps import SettingsDep
from graphrev.schemas.config import AppConfigDto, app_config_from_settings

router = APIRouter(tags=["config"])


@router.get("/config", response_model=AppConfigDto)
async def get_config(settings: SettingsDep) -> AppConfigDto:
    return app_config_from_settings(settings)
