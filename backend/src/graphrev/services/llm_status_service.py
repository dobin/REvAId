"""Application service for passive LLM worker status."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.adapters.llm.base import LlmAdapter
from graphrev.core.config import Settings
from graphrev.repositories.llm_status import get_worker_status
from graphrev.schemas.llm_status import LlmProbeDto, LlmStatusDto


async def get_passive_status(session: AsyncSession, settings: Settings) -> LlmStatusDto:
    """Read persisted worker evidence without contacting the provider."""
    status = await get_worker_status(
        session, adapter=settings.llm_adapter, model=settings.llm_model
    )
    if status is None:
        return LlmStatusDto(
            adapter=settings.llm_adapter,
            model=settings.llm_model,
            outcome="no_outcome",
        )
    return LlmStatusDto(
        adapter=status.adapter,
        model=status.model,
        outcome=status.outcome,
        observed_at=status.observed_at,
        error_code=status.error_code,
    )


async def probe(adapter: LlmAdapter) -> LlmProbeDto:
    """Run the adapter's deliberately explicit live probe without persisting it."""
    health = await adapter.health()
    return LlmProbeDto(reachable=health.reachable, detail=health.detail)