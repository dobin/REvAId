"""PRAGMA verification: foreign_keys=ON and WAL mode, per connection."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_foreign_keys_and_wal_enabled(session: AsyncSession) -> None:
    fk = (await session.execute(text("PRAGMA foreign_keys"))).scalar()
    jm = (await session.execute(text("PRAGMA journal_mode"))).scalar()
    assert fk == 1
    assert jm == "wal"


@pytest.mark.asyncio
async def test_foreign_key_violation_raises(session: AsyncSession) -> None:
    """B17's FK integrity guarantee depends on foreign_keys being ON."""
    with pytest.raises(IntegrityError):
        await session.execute(
            text(
                "INSERT INTO edges (binary_id, caller_id, callee_id, kind) "
                "VALUES (999999, 999999, 999999, 'call')"
            )
        )
        await session.commit()
