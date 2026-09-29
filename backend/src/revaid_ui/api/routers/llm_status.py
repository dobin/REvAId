"""Viewer proxies for analysis-owned LLM status."""

from __future__ import annotations

from fastapi import APIRouter

from revaid_contracts.schemas.llm_status import LlmProbeDto, LlmStatusDto
from revaid_ui.api.deps import AnalysisClientDep

router = APIRouter(tags=["llm-status"])


@router.get("/llm-status", response_model=LlmStatusDto)
async def get_llm_status(analysis: AnalysisClientDep) -> LlmStatusDto:
    return LlmStatusDto.model_validate(await analysis.get_llm_status())


@router.post("/llm-status/probe", response_model=LlmProbeDto)
async def probe_llm_status(analysis: AnalysisClientDep) -> LlmProbeDto:
    return LlmProbeDto.model_validate(await analysis.probe_llm())
