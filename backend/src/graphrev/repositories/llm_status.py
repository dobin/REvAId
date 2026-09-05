"""Persistence for passive LLM worker-status diagnostics."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.db.enums import LlmWorkerOutcome
from graphrev.db.models import LlmWorkerStatus


async def record_worker_outcome(
    session: AsyncSession,
    *,
    adapter: str,
    model: str,
    outcome: LlmWorkerOutcome,
    observed_at: str,
    function_id: int,
    error_code: str | None = None,
) -> None:
    """Upsert the latest safe, meaningful provider result for this config."""
    stmt = sqlite_insert(LlmWorkerStatus).values(
        adapter=adapter,
        model=model,
        outcome=outcome,
        observed_at=observed_at,
        function_id=function_id,
        error_code=error_code,
    )
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[LlmWorkerStatus.adapter, LlmWorkerStatus.model],
            set_={
                "outcome": stmt.excluded.outcome,
                "observed_at": stmt.excluded.observed_at,
                "function_id": stmt.excluded.function_id,
                "error_code": stmt.excluded.error_code,
            },
        )
    )


async def get_worker_status(
    session: AsyncSession, *, adapter: str, model: str
) -> LlmWorkerStatus | None:
    result = await session.execute(
        select(LlmWorkerStatus).where(
            LlmWorkerStatus.adapter == adapter,
            LlmWorkerStatus.model == model,
        )
    )
    return result.scalar_one_or_none()