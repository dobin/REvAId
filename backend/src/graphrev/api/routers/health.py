"""``GET /health`` (F4) — DB and adapter status."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from graphrev.adapters.llm.base import LlmHealth
from graphrev.api.deps import LlmAdapterDep, SessionDep, SettingsDep
from graphrev.schemas.config import HealthDto, LlmHealthDto

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthDto)
async def get_health(
    session: SessionDep, settings: SettingsDep, llm_adapter: LlmAdapterDep
) -> HealthDto:
    db_ok = True
    revision: str | None = None
    try:
        await session.execute(text("SELECT 1"))
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        revision = result.scalar_one_or_none()
    except Exception:  # pragma: no cover - defensive; health must never 500
        db_ok = False

    # AM5: report adapter reachability, not just its name — the UI must be
    # able to tell "no summaries because misconfigured" from "no summaries
    # yet". `health()` never raises by contract; the guard is defensive.
    try:
        llm_health: LlmHealth = await llm_adapter.health()
    except Exception:  # pragma: no cover - defensive; health must never 500
        llm_health = LlmHealth(reachable=False, detail="health check raised")

    return HealthDto(
        status="ok" if db_ok else "degraded",
        db_ok=db_ok,
        migration_revision=revision,
        ghidra_adapter=settings.ghidra_adapter,
        llm_adapter=settings.llm_adapter,
        llm_health=LlmHealthDto(reachable=llm_health.reachable, detail=llm_health.detail),
    )
