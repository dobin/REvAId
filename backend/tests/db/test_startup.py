"""C5b restart recovery and F1b threshold-change recompute."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from revaid.core.clock import utc_now_iso
from revaid.core.config import Settings
from revaid.db.models import Binary, Function
from revaid.db.startup import recompute_utility_if_threshold_changed, recover_pending_summaries
from revaid.summarization.queue import MAX_PRIORITY, SummaryQueue
from revaid_contracts.analysis import AnalysisBinary
from revaid_ui.db.models import BinaryUiState, View, ViewNode
from revaid_ui.db.startup import reconcile_viewer_state


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
        name="a",
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
async def test_reconcile_viewer_state_clears_stale_external_references(
    session: AsyncSession, viewer_session: AsyncSession
) -> None:
    binaries = [
        Binary(name=f"binary-{index}", version="1", created_at=_now(), updated_at=_now())
        for index in range(3)
    ]
    session.add_all(binaries)
    await session.flush()
    await session.commit()
    first_view = View(binary_id=binaries[0].id, name="First", created_at=_now(), updated_at=_now())
    other_view = View(binary_id=binaries[1].id, name="Other", created_at=_now(), updated_at=_now())
    viewer_session.add_all([first_view, other_view])
    await viewer_session.flush()

    viewer_session.add_all(
        [
            BinaryUiState(
                binary_id=binaries[0].id,
                last_view_id=first_view.id,
                updated_at=_now(),
            ),
            BinaryUiState(
                binary_id=binaries[1].id,
                last_view_id=first_view.id,
                updated_at=_now(),
            ),
            BinaryUiState(
                binary_id=binaries[2].id,
                last_view_id=999999,
                updated_at=_now(),
            ),
            BinaryUiState(binary_id=999999, last_view_id=1, updated_at=_now()),
            ViewNode(
                view_id=first_view.id,
                function_id=777777,
                origin_function_id=777778,
                origin_kind="fanout",
                created_at=_now(),
                updated_at=_now(),
            ),
        ]
    )
    await viewer_session.commit()

    class StubAnalysisClient:
        async def get_binary(self, binary_id: int) -> AnalysisBinary | None:
            binary = next((row for row in binaries if row.id == binary_id), None)
            if binary is None:
                return None
            return AnalysisBinary(
                id=binary.id,
                name=binary.name,
                version=binary.version,
                analysis_image_base=None,
            )

        async def validate_function_membership(
            self, binary_id: int, function_ids: list[int]
        ) -> set[int]:
            return set()

        async def resolve_addresses(
            self, binary_id: int, addresses: list[int]
        ) -> dict[int, object]:
            return {}

        async def get_featured_graph(self, binary_id: int) -> object:
            raise AssertionError

        async def get_neighbours(self, query: object) -> object:
            raise AssertionError

        async def get_function(self, function_id: int) -> object:
            return None

    analysis_client = StubAnalysisClient()
    changed = await reconcile_viewer_state(analysis_client, viewer_session)  # type: ignore[arg-type]
    assert changed >= 4
    assert await viewer_session.get(BinaryUiState, binaries[0].id) is not None
    wrong_binary_state = await viewer_session.get(BinaryUiState, binaries[1].id)
    assert wrong_binary_state is not None and wrong_binary_state.last_view_id is None
    missing_view_state = await viewer_session.get(BinaryUiState, binaries[2].id)
    assert missing_view_state is not None and missing_view_state.last_view_id is None
    assert await viewer_session.get(BinaryUiState, 999999) is None
    assert await viewer_session.get(View, first_view.id) is not None
    assert (await viewer_session.execute(select(ViewNode))).first() is None

    # Startup repair is safe to retry after a partial run or restart.
    assert await reconcile_viewer_state(analysis_client, viewer_session) == 0  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_reconcile_viewer_state_removes_view_for_missing_binary(
    viewer_session: AsyncSession,
) -> None:
    view = View(binary_id=999999, name="Orphan", created_at=_now(), updated_at=_now())
    viewer_session.add(view)
    await viewer_session.flush()
    viewer_session.add(
        ViewNode(
            view_id=view.id,
            function_id=1,
            created_at=_now(),
            updated_at=_now(),
        )
    )
    await viewer_session.commit()

    class MissingAnalysisClient:
        async def get_binary(self, binary_id: int) -> AnalysisBinary | None:
            return None

        async def validate_function_membership(
            self, binary_id: int, function_ids: list[int]
        ) -> set[int]:
            return set()

    changed = await reconcile_viewer_state(MissingAnalysisClient(), viewer_session)  # type: ignore[arg-type]
    assert changed == 1
    assert await viewer_session.get(View, view.id) is None
    assert (await viewer_session.execute(select(ViewNode))).first() is None


@pytest.mark.asyncio
async def test_recover_pending_summaries_leaves_other_statuses(session: AsyncSession) -> None:
    binary = Binary(name="acme.exe", version="1.0", created_at=_now(), updated_at=_now())
    session.add(binary)
    await session.flush()
    fn = Function(
        binary_id=binary.id,
        address=0x1,
        name="a",
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
            name=f"fn_{address}",
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
        name="a",
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
