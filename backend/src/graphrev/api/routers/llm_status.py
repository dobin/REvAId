"""Passive LLM worker status and deliberately explicit live probing."""

from __future__ import annotations

from fastapi import APIRouter

from graphrev.api.deps import LlmAdapterDep, SessionDep, SettingsDep
from graphrev.schemas.llm_status import LlmProbeDto, LlmStatusDto
from graphrev.services import llm_status_service

router = APIRouter(tags=["llm-status"])


@router.get("/llm-status", response_model=LlmStatusDto)
async def get_llm_status(session: SessionDep, settings: SettingsDep) -> LlmStatusDto:
    """Return recent worker evidence only; this endpoint never probes an LLM."""
    return await llm_status_service.get_passive_status(session, settings)


@router.post("/llm-status/probe", response_model=LlmProbeDto)
async def probe_llm_status(adapter: LlmAdapterDep) -> LlmProbeDto:
    """Run one user-requested live reachability probe without changing worker status."""
    return await llm_status_service.probe(adapter)