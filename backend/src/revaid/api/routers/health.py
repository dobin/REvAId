"""``GET /health`` (F4) — DB and adapter status."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from revaid.adapters.llm.base import LlmHealth
from revaid.api.deps import LlmAdapterDep, SessionDep, SettingsDep
from revaid.db.startup import ANALYSIS_MIGRATION_REVISION
from revaid.services.decompiler_health import check_decompiler_health
from revaid_contracts.schemas.config import DecompilerHealthDto, HealthDto, LlmHealthDto

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthDto)
async def get_health(
    settings: SettingsDep,
    session: SessionDep,
    llm_adapter: LlmAdapterDep,
) -> HealthDto:
    db_ok = True
    revision: str | None = None
    try:
        await session.execute(text("SELECT 1"))
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        revision = result.scalar_one_or_none()
        db_ok = revision == ANALYSIS_MIGRATION_REVISION
    except Exception:  # pragma: no cover - defensive; health must never 500
        db_ok = False

    # AM5: report adapter reachability, not just its name — the UI must be
    # able to tell "no summaries because misconfigured" from "no summaries
    # yet". `health()` never raises by contract; the guard is defensive.
    try:
        llm_health: LlmHealth = (
            await llm_adapter.health()
            if llm_adapter is not None
            else LlmHealth(reachable=False, detail="analysis service not configured")
        )
    except Exception:  # pragma: no cover - defensive; health must never 500
        llm_health = LlmHealth(reachable=False, detail="health check raised")
    reachable, detail = await check_decompiler_health(settings.decompiler_executable)
    decompiler_health = DecompilerHealthDto(reachable=reachable, detail=detail)

    return HealthDto(
        status="ok" if db_ok else "degraded",
        db_ok=db_ok,
        migration_revision=revision,
        viewer_db_ok=False,
        viewer_migration_revision=None,
        ghidra_adapter=settings.ghidra_adapter,
        llm_adapter=settings.llm_adapter,
        llm_health=LlmHealthDto(reachable=llm_health.reachable, detail=llm_health.detail),
        decompiler_health=decompiler_health,
    )
