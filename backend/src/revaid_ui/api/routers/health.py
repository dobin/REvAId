"""``GET /health`` (F4) — DB and adapter status."""

from __future__ import annotations

from contextlib import suppress

from fastapi import APIRouter
from sqlalchemy import text

from revaid_contracts.schemas.config import DecompilerHealthDto, HealthDto, LlmHealthDto
from revaid_ui.api.deps import AnalysisClientDep, ViewerSessionDep
from revaid_ui.db.revision import VIEWER_MIGRATION_REVISION

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthDto)
async def get_health(
    viewer_session: ViewerSessionDep,
    analysis: AnalysisClientDep,
) -> HealthDto:
    viewer_revision: str | None = None
    viewer_db_ok = True
    try:
        await viewer_session.execute(text("SELECT 1"))
        result = await viewer_session.execute(text("SELECT version_num FROM alembic_version"))
        viewer_revision = result.scalar_one_or_none()
        viewer_db_ok = viewer_revision == VIEWER_MIGRATION_REVISION
    except Exception:  # health should report degradation instead of raising
        viewer_db_ok = False
    analysis_ok = False
    analysis_health: dict[str, object] = {}
    with suppress(Exception):
        analysis_health = await analysis.health_details()
        analysis_ok = analysis_health.get("status") == "ok"
    decompiler_health = analysis_health.get(
        "decompiler_health",
        {
            "reachable": False,
            "detail": "Decompiler health unavailable from analysis service.",
        },
    )
    if not isinstance(decompiler_health, dict):
        decompiler_health = {}
    analysis_config = {}
    with suppress(Exception):
        analysis_config = await analysis.config()
    analysis_revision = None
    with suppress(Exception):
        analysis_revision = await analysis.migration_revision()
    adapters = analysis_config.get("adapters", {})
    if not isinstance(adapters, dict):
        adapters = {}
    return HealthDto(
        status="ok" if viewer_db_ok and analysis_ok else "degraded",
        db_ok=viewer_db_ok and analysis_ok,
        migration_revision=analysis_revision,
        viewer_db_ok=viewer_db_ok,
        viewer_migration_revision=viewer_revision,
        ghidra_adapter=str(adapters.get("ghidra", "analysis")),
        llm_adapter=str(adapters.get("llm", "analysis")),
        llm_health=LlmHealthDto(reachable=analysis_ok, detail=None),
        decompiler_health=DecompilerHealthDto(
            reachable=decompiler_health.get("reachable") is True,
            detail=(
                str(decompiler_health["detail"])
                if decompiler_health.get("detail") is not None
                else None
            ),
        ),
    )
