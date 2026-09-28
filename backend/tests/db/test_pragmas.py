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
async def test_viewer_foreign_keys_and_wal_enabled(viewer_session: AsyncSession) -> None:
    fk = (await viewer_session.execute(text("PRAGMA foreign_keys"))).scalar()
    jm = (await viewer_session.execute(text("PRAGMA journal_mode"))).scalar()
    assert fk == 1
    assert jm == "wal"


@pytest.mark.asyncio
async def test_viewer_view_node_local_foreign_key_is_enforced(
    viewer_session: AsyncSession,
) -> None:
    with pytest.raises(IntegrityError):
        await viewer_session.execute(
            text(
                "INSERT INTO view_nodes "
                "(view_id, function_id, visible, collapsed, pos_x, pos_y, pinned, "
                "origin_kind, origin_implied, created_at, updated_at) "
                "VALUES (999999, 123456, 1, 0, 0, 0, 0, 'root', 0, 'now', 'now')"
            )
        )
        await viewer_session.commit()


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
