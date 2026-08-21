"""``GET /health`` (F4) — DB and adapter status."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from graphrev.api.deps import SessionDep, SettingsDep
from graphrev.schemas.config import HealthDto

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthDto)
async def get_health(session: SessionDep, settings: SettingsDep) -> HealthDto:
    db_ok = True
    revision: str | None = None
    try:
        await session.execute(text("SELECT 1"))
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        revision = result.scalar_one_or_none()
    except Exception:  # pragma: no cover - defensive; health must never 500
        db_ok = False

    return HealthDto(
        status="ok" if db_ok else "degraded",
        db_ok=db_ok,
        migration_revision=revision,
        ghidra_adapter=settings.ghidra_adapter,
        llm_adapter=settings.llm_adapter,
    )
