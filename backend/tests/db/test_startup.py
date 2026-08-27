"""C5b restart recovery and F1b threshold-change recompute."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.core.config import Settings
from graphrev.db.models import Binary, Function
from graphrev.db.startup import recompute_utility_if_threshold_changed, recover_pending_summaries
from graphrev.summarization.queue import MAX_PRIORITY, SummaryQueue


def _now() -> str:
    return utc_now_iso()


@pytest.mark.asyncio
async def test_recover_pending_summaries_requeues_pending_work(session: AsyncSession) -> None:
    binary = Binary(name="acme.exe", version="1.0", created_at=_now(), updated_at=_now())
    session.add(binary)
    await session.flush()
    fn = Function(
        binary_id=binary.id,
        address=0x1,
        name_ghidra="a",
        summary_status="pending",
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(fn)
    await session.commit()

    queue = SummaryQueue(max_depth=10)
    count = await recover_pending_summaries(session, queue)
    assert count == 1

    await session.refresh(fn)
    assert fn.summary_status == "pending"
    item = await queue.pop()
    assert item.function_id == fn.id
    assert item.priority == MAX_PRIORITY


@pytest.mark.asyncio
async def test_recover_pending_summaries_leaves_other_statuses(session: AsyncSession) -> None:
    binary = Binary(name="acme.exe", version="1.0", created_at=_now(), updated_at=_now())
    session.add(binary)
    await session.flush()
    fn = Function(
        binary_id=binary.id,
        address=0x1,
        name_ghidra="a",
        summary_status="ready",
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(fn)
    await session.commit()

    queue = SummaryQueue(max_depth=10)
    await recover_pending_summaries(session, queue)
    await session.refresh(fn)
    assert fn.summary_status == "ready"
    assert queue.depth() == 0


@pytest.mark.asyncio
async def test_recover_pending_summaries_resets_rows_evicted_by_reduced_capacity(
    session: AsyncSession,
) -> None:
    binary = Binary(name="acme.exe", version="1.0", created_at=_now(), updated_at=_now())
    session.add(binary)
    await session.flush()
    functions = [
        Function(
            binary_id=binary.id,
            address=address,
            name_ghidra=f"fn_{address}",
            summary_status="pending",
            created_at=_now(),
            updated_at=_now(),
        )
        for address in (0x1, 0x2)
    ]
    session.add_all(functions)
    await session.commit()

    queue = SummaryQueue(max_depth=1)
    count = await recover_pending_summaries(session, queue)
    assert count == 1

    for fn in functions:
        await session.refresh(fn)
    assert sum(fn.summary_status == "pending" for fn in functions) == 1
    assert sum(fn.summary_status == "none" for fn in functions) == 1


@pytest.mark.asyncio
async def test_recompute_utility_noop_when_threshold_unchanged(
    session: AsyncSession, settings: Settings
) -> None:
    # 0001_initial seeds app_meta with the *default* threshold at migration
    # time, which matches settings.utility_fanin_threshold in this fixture.
    changed = await recompute_utility_if_threshold_changed(session, settings)
    assert changed is False


@pytest.mark.asyncio
async def test_recompute_utility_flips_is_utility_when_threshold_changes(
    session: AsyncSession, settings: Settings
) -> None:
    binary = Binary(name="acme.exe", version="1.0", created_at=_now(), updated_at=_now())
    session.add(binary)
    await session.flush()
    fn = Function(
        binary_id=binary.id,
        address=0x1,
        name_ghidra="a",
        fan_in=40,
        is_utility=False,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(fn)
    await session.commit()

    # Lower the threshold below fan_in=40 and simulate a restart with the new setting.
    settings.utility_fanin_threshold = 30

    changed = await recompute_utility_if_threshold_changed(session, settings)
    assert changed is True

    await session.refresh(fn)
    assert fn.is_utility is True

    stored = (
        await session.execute(
            text("SELECT value FROM app_meta WHERE key = 'utility_fanin_threshold'")
        )
    ).scalar_one()
    assert stored == "30"

    # A second call with the same (now-current) threshold must be a no-op.
    changed_again = await recompute_utility_if_threshold_changed(session, settings)
    assert changed_again is False
