"""Post-ingest mock-summary seeding (CLI-only dev/demo affordance).

Inject fake LLM summaries directly into the DB so the UI shows plausible
analyst content without running the real summarisation queue. Lives in
`ingestion` rather than `adapters/ghidra/mock.py` because it is *not* part
of the adapter — it performs DB I/O against ``graphrev.db.models`` and is
called by ``graphrev.cli.ingest``, which may not import a concrete adapter
implementation (``adapters/ghidra/mock``) directly (import-linter contract).
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graphrev.adapters.mock_summaries import MOCK_LLM_NAMES, MOCK_SUMMARIES
from graphrev.db.models import Function


async def seed_mock_summaries(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Inject fake LLM summaries into the DB for UI development.

    Only updates rows where *summary_status* is still ``'none'`` so a real
    summarisation run is not overwritten.  Returns the number of rows updated.
    """
    updated = 0
    async with session_factory() as session, session.begin():
        for name, (short, long_) in MOCK_SUMMARIES.items():
            result = await session.execute(
                select(Function.id).where(
                    Function.name_ghidra == name,
                    Function.summary_status == "none",
                )
            )
            ids = [row[0] for row in result.all()]
            if not ids:
                continue
            await session.execute(
                update(Function)
                .where(Function.id.in_(ids))
                .values(
                    summary_short=short,
                    summary_long=long_,
                    name_llm=MOCK_LLM_NAMES.get(name),
                    summary_status="ready",
                    summary_model="mock-llm-v1",
                    summary_generated_at="2026-08-22T00:00:00Z",
                )
            )
            updated += len(ids)
    return updated
