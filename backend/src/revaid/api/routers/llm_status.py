"""Passive LLM worker status and deliberately explicit live probing."""

from __future__ import annotations

from fastapi import APIRouter

from revaid.api.deps import LlmAdapterDep, SessionDep, SettingsDep
from revaid.schemas.llm_status import LlmProbeDto, LlmStatusDto
from revaid.services import llm_status_service

router = APIRouter(tags=["llm-status"])


@router.get("/llm-status", response_model=LlmStatusDto)
async def get_llm_status(
    settings: SettingsDep,
    session: SessionDep,
) -> LlmStatusDto:
    """Return recent worker evidence only; this endpoint never probes an LLM."""
    assert session is not None
    return await llm_status_service.get_passive_status(session, settings)


@router.post("/llm-status/probe", response_model=LlmProbeDto)
async def probe_llm_status(
    adapter: LlmAdapterDep,
) -> LlmProbeDto:
    """Run one user-requested live reachability probe without changing worker status."""
    assert adapter is not None
    return await llm_status_service.probe(adapter)
