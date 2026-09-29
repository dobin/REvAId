"""``GET /config`` (E1d)."""

from __future__ import annotations

from fastapi import APIRouter

from revaid_contracts.schemas.config import AppConfigDto
from revaid_ui.api.deps import AnalysisClientDep

router = APIRouter(tags=["config"])


@router.get("/config", response_model=AppConfigDto)
async def get_config(analysis: AnalysisClientDep) -> AppConfigDto:
    config = await analysis.config()
    if "utilityFanInThreshold" in config:
        config = {**config, "utility_fanin_threshold": config["utilityFanInThreshold"]}
    return AppConfigDto.model_validate(config)
