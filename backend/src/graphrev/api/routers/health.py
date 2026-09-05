"""``GET /health`` (F4) — DB and adapter status."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import text

from graphrev.adapters.llm.base import LlmHealth
from graphrev.api.deps import LlmAdapterDep, SessionDep, SettingsDep
from graphrev.schemas.config import DecompilerHealthDto, HealthDto, LlmHealthDto

router = APIRouter(tags=["health"])


async def _decompiler_health(executable: str | None) -> DecompilerHealthDto:
    """Verify configured Kuna path and version without analyzing a binary."""
    if not executable:
        return DecompilerHealthDto(
            reachable=False, detail="No decompiler executable is configured."
        )
    path = Path(executable)
    if not path.is_file():
        return DecompilerHealthDto(
            reachable=False, detail="Configured decompiler path is not a file."
        )
    if not path.stat().st_mode & 0o111:
        return DecompilerHealthDto(
            reachable=False, detail="Configured decompiler is not executable."
        )
    try:
        process = await asyncio.create_subprocess_exec(
            str(path),
            "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        output, _ = await asyncio.wait_for(process.communicate(), timeout=5)
    except (OSError, TimeoutError):
        return DecompilerHealthDto(reachable=False, detail="Could not run configured decompiler.")
    version = output.decode("utf-8", errors="replace").strip()
    if process.returncode != 0:
        return DecompilerHealthDto(
            reachable=False, detail="Configured decompiler version check failed."
        )
    if "kuna" not in version.lower():
        return DecompilerHealthDto(reachable=False, detail="Configured executable is not Kuna.")
    return DecompilerHealthDto(reachable=True, detail=version[:200] or "Kuna is available.")


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
    decompiler_health = await _decompiler_health(settings.decompiler_executable)

    return HealthDto(
        status="ok" if db_ok else "degraded",
        db_ok=db_ok,
        migration_revision=revision,
        ghidra_adapter=settings.ghidra_adapter,
        llm_adapter=settings.llm_adapter,
        llm_health=LlmHealthDto(reachable=llm_health.reachable, detail=llm_health.detail),
        decompiler_health=decompiler_health,
    )
