"""I4: `repositories.neighbours.fetch_neighbour_page` (E2, E2a, E2b, D7, D34)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Binary, Edge, Function, View, ViewNode
from graphrev.repositories.neighbours import fetch_neighbour_page


def _now() -> str:
    return utc_now_iso()


async def _make_binary(session: AsyncSession, name: str = "acme.exe") -> Binary:
    binary = Binary(name=name, version="1.0", created_at=_now(), updated_at=_now())
    session.add(binary)
    await session.flush()
    return binary


async def _make_function(
    session: AsyncSession,
    binary: Binary,
    address: int,
    name: str,
    *,
    is_utility: bool = False,
    utility_override: str | None = None,
    fan_in: int = 0,
    summary_short: str | None = None,
) -> Function:
    fn = Function(
        binary_id=binary.id,
        address=address,
        name_ghidra=name,
        is_utility=is_utility,
        utility_override=utility_override,
        fan_in=fan_in,
        summary_short=summary_short,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(fn)
    await session.flush()
    return fn


async def _make_view(session: AsyncSession, binary: Binary) -> View:
    view = View(binary_id=binary.id, name="Default", created_at=_now(), updated_at=_now())
    session.add(view)
    await session.flush()
    return view


async def _add_edge(
    session: AsyncSession, binary: Binary, caller: Function, callee: Function
) -> None:
    session.add(Edge(binary_id=binary.id, caller_id=caller.id, callee_id=callee.id))
    await session.flush()


@pytest.mark.asyncio
async def test_callees_split_into_primary_and_utility_groups(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    view = await _make_view(session, binary)
    root = await _make_function(session, binary, 0x1000, "root")
    primary = await _make_function(session, binary, 0x1010, "helper", is_utility=False)
    utility = await _make_function(session, binary, 0x1020, "memcpy_like", is_utility=True)
    await _add_edge(session, binary, root, primary)
    await _add_edge(session, binary, root, utility)
    await session.commit()

    primary_page = await fetch_neighbour_page(
        session,
        function_id=root.id,
        view_id=view.id,
        direction="callees",
        group="primary",
        limit=16,
        offset=0,
        sort="name",
        order="asc",
        filter_text=None,
        caller_suppress_threshold=32,
    )
    assert primary_page.total == 1
    assert primary_page.total_primary == 1
    assert primary_page.total_utility == 1
    assert [r.function.name_ghidra for r in primary_page.rows] == ["helper"]

    utility_page = await fetch_neighbour_page(
        session,
        function_id=root.id,
        view_id=view.id,
        direction="callees",
        group="utility",
        limit=16,
        offset=0,
        sort="name",
        order="asc",
        filter_text=None,
        caller_suppress_threshold=32,
    )
    assert utility_page.total == 1
    assert [r.function.name_ghidra for r in utility_page.rows] == ["memcpy_like"]


@pytest.mark.asyncio
async def test_utility_override_moves_row_between_groups(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    view = await _make_view(session, binary)
    root = await _make_function(session, binary, 0x1000, "root")
    fn = await _make_function(
        session, binary, 0x1010, "special_case", is_utility=True, utility_override="never"
    )
    await _add_edge(session, binary, root, fn)
    await session.commit()

    primary_page = await fetch_neighbour_page(
        session,
        function_id=root.id,
        view_id=view.id,
        direction="callees",
        group="primary",
        limit=16,
        offset=0,
        sort="name",
        order="asc",
        filter_text=None,
        caller_suppress_threshold=32,
    )
    assert [r.function.name_ghidra for r in primary_page.rows] == ["special_case"]


@pytest.mark.asyncio
async def test_caller_table_suppressed_beyond_threshold_never_fetches_rows(
    session: AsyncSession,
) -> None:
    binary = await _make_binary(session)
    view = await _make_view(session, binary)
    target = await _make_function(session, binary, 0x2000, "hub")
    for i in range(35):
        caller = await _make_function(session, binary, 0x3000 + i, f"caller_{i}")
        await _add_edge(session, binary, caller, target)
    await session.commit()

    page = await fetch_neighbour_page(
        session,
        function_id=target.id,
        view_id=view.id,
        direction="callers",
        group="primary",
        limit=16,
        offset=0,
        sort="name",
        order="asc",
        filter_text=None,
        caller_suppress_threshold=32,
    )
    assert page.callers_suppressed is True
    assert page.rows == []
    assert page.total == 35


@pytest.mark.asyncio
async def test_caller_table_not_suppressed_below_threshold(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    view = await _make_view(session, binary)
    target = await _make_function(session, binary, 0x2000, "hub")
    for i in range(5):
        caller = await _make_function(session, binary, 0x3000 + i, f"caller_{i}")
        await _add_edge(session, binary, caller, target)
    await session.commit()

    page = await fetch_neighbour_page(
        session,
        function_id=target.id,
        view_id=view.id,
        direction="callers",
        group="primary",
        limit=16,
        offset=0,
        sort="name",
        order="asc",
        filter_text=None,
        caller_suppress_threshold=32,
    )
    assert page.callers_suppressed is False
    assert len(page.rows) == 5
    assert page.total == 5


@pytest.mark.asyncio
async def test_on_canvas_reflects_view_scoped_visible_view_node(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    view = await _make_view(session, binary)
    other_view = await _make_view(session, binary)
    root = await _make_function(session, binary, 0x1000, "root")
    placed = await _make_function(session, binary, 0x1010, "placed_fn")
    not_placed = await _make_function(session, binary, 0x1020, "not_placed_fn")
    await _add_edge(session, binary, root, placed)
    await _add_edge(session, binary, root, not_placed)
    session.add(
        ViewNode(
            view_id=view.id,
            function_id=placed.id,
            visible=True,
            created_at=_now(),
            updated_at=_now(),
        )
    )
    # A placement in a *different* view must not leak into this view's page.
    session.add(
        ViewNode(
            view_id=other_view.id,
            function_id=not_placed.id,
            visible=True,
            created_at=_now(),
            updated_at=_now(),
        )
    )
    await session.commit()

    page = await fetch_neighbour_page(
        session,
        function_id=root.id,
        view_id=view.id,
        direction="callees",
        group="primary",
        limit=16,
        offset=0,
        sort="name",
        order="asc",
        filter_text=None,
        caller_suppress_threshold=32,
    )
    on_canvas_by_name = {r.function.name_ghidra: r.on_canvas for r in page.rows}
    assert on_canvas_by_name["placed_fn"] is True
    assert on_canvas_by_name["not_placed_fn"] is False


@pytest.mark.asyncio
async def test_filter_matches_name_and_summary_short(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    view = await _make_view(session, binary)
    root = await _make_function(session, binary, 0x1000, "root")
    matching_name = await _make_function(session, binary, 0x1010, "parse_config")
    matching_summary = await _make_function(
        session, binary, 0x1020, "other_fn", summary_short="Parses the header"
    )
    non_matching = await _make_function(session, binary, 0x1030, "unrelated")
    for callee in (matching_name, matching_summary, non_matching):
        await _add_edge(session, binary, root, callee)
    await session.commit()

    page = await fetch_neighbour_page(
        session,
        function_id=root.id,
        view_id=view.id,
        direction="callees",
        group="primary",
        limit=16,
        offset=0,
        sort="name",
        order="asc",
        filter_text="parse",
        caller_suppress_threshold=32,
    )
    names = {r.function.name_ghidra for r in page.rows}
    assert names == {"parse_config", "other_fn"}
    # Unfiltered group totals must not shift because of the filter text.
    assert page.total_primary == 3
    assert page.total == 2


@pytest.mark.asyncio
async def test_sort_by_fan_in_descending(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    view = await _make_view(session, binary)
    root = await _make_function(session, binary, 0x1000, "root")
    low = await _make_function(session, binary, 0x1010, "low_fanin", fan_in=1)
    high = await _make_function(session, binary, 0x1020, "high_fanin", fan_in=99)
    await _add_edge(session, binary, root, low)
    await _add_edge(session, binary, root, high)
    await session.commit()

    page = await fetch_neighbour_page(
        session,
        function_id=root.id,
        view_id=view.id,
        direction="callees",
        group="primary",
        limit=16,
        offset=0,
        sort="fanIn",
        order="desc",
        filter_text=None,
        caller_suppress_threshold=32,
    )
    assert [r.function.name_ghidra for r in page.rows] == ["high_fanin", "low_fanin"]


@pytest.mark.asyncio
async def test_get_does_not_mutate_summary_status(session: AsyncSession) -> None:
    """C2c/Q23: the neighbour read must never enqueue/mutate summary state."""
    binary = await _make_binary(session)
    view = await _make_view(session, binary)
    root = await _make_function(session, binary, 0x1000, "root")
    callee = await _make_function(session, binary, 0x1010, "callee")
    await _add_edge(session, binary, root, callee)
    await session.commit()

    before = (
        await session.execute(select(Function.summary_status).where(Function.id == callee.id))
    ).scalar_one()

    await fetch_neighbour_page(
        session,
        function_id=root.id,
        view_id=view.id,
        direction="callees",
        group="primary",
        limit=16,
        offset=0,
        sort="name",
        order="asc",
        filter_text=None,
        caller_suppress_threshold=32,
    )

    after = (
        await session.execute(select(Function.summary_status).where(Function.id == callee.id))
    ).scalar_one()
    assert before == after == "none"
