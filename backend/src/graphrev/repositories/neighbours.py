"""The neighbour-table query (E2, E2a, E2b) — TAD §4.3's "most important read".

A single indexed SELECT per call, side-effect free (E2/C2c — this module must
never enqueue or otherwise mutate `summary_status`; it only reads). Direction
is handled generically: "callees" joins `edges.callee_id` to the neighbour
function with `edges.caller_id = function_id`; "callers" is the mirror image.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import ColumnElement, String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.db.models import Edge, Function, ViewNode

Direction = Literal["callees", "callers"]
Group = Literal["primary", "utility"]
SortKey = Literal["callOrder", "name", "address", "fanIn"]
SortOrder = Literal["asc", "desc"]


@dataclass(frozen=True, slots=True)
class NeighbourQueryResult:
    rows: list[NeighbourRow]
    total: int
    total_primary: int
    total_utility: int
    callers_suppressed: bool


@dataclass(frozen=True, slots=True)
class NeighbourRow:
    """One neighbour row plus the view-scoped/derived fields the DTO needs."""

    function: Function
    on_canvas: bool
    is_self: bool


#: Sort-key -> the SQL expression it orders by (D23). "name" sorts by the
#: visible display name (`name_analyst ?? name_llm ?? name_ghidra`), matching
#: `function_dto_from_row`'s `display_name` derivation.
_SORT_EXPRESSIONS: dict[Literal["name", "address", "fanIn"], ColumnElement[object]] = {
    "name": func.coalesce(Function.name_analyst, Function.name_llm, Function.name_ghidra),
    "address": Function.address,  # type: ignore[dict-item]
    "fanIn": Function.fan_in,  # type: ignore[dict-item]
}


def _direction_columns(direction: Direction) -> tuple[ColumnElement[object], ColumnElement[object]]:
    """`(this_side, other_side)` edge columns for `direction`.

    For "callees": `edges.caller_id` is this function, `edges.callee_id` is
    the neighbour. For "callers", the mirror image.
    """
    if direction == "callees":
        return Edge.caller_id, Edge.callee_id  # type: ignore[return-value]
    return Edge.callee_id, Edge.caller_id  # type: ignore[return-value]


async def _count_edges(
    session: AsyncSession, *, this_side: ColumnElement[object], function_id: int
) -> int:
    """Total edge count in one direction, ungrouped/unfiltered — the number
    D7 suppression compares against, and the number shown in the suppression
    notice ("Called by 291")."""
    result = await session.execute(
        select(func.count()).where(this_side == function_id, Edge.kind == "call")
    )
    return result.scalar_one()


async def fetch_neighbour_page(
    session: AsyncSession,
    *,
    function_id: int,
    view_id: int,
    direction: Direction,
    group: Group,
    limit: int,
    offset: int,
    sort: SortKey,
    order: SortOrder,
    filter_text: str | None,
    caller_suppress_threshold: int,
) -> NeighbourQueryResult:
    """The E2 neighbour-table read.

    `total`/`totalPrimary`/`totalUtility` semantics (TAD §4.3 payload):
      * `totalPrimary`/`totalUtility` are the **unfiltered** group sizes —
        stable header counts (e.g. the collapsed `▸ ▫ utility calls (N)`
        badge) that must not shift as the analyst types into the filter box.
      * `total` is the filtered count for the requested `group` — "showing
        16 of `total`" pagination math.

    D7/E2a: for `direction="callers"`, if the *ungrouped* caller count
    exceeds `caller_suppress_threshold`, the query short-circuits before
    ever fetching or grouping the 291 rows — `rows` is `[]`,
    `callers_suppressed` is `True`, and `total` is that ungrouped count (the
    number the one-line notice displays).
    """
    this_side, other_side = _direction_columns(direction)

    if direction == "callers":
        ungrouped_total = await _count_edges(session, this_side=this_side, function_id=function_id)
        if ungrouped_total > caller_suppress_threshold:
            return NeighbourQueryResult(
                rows=[],
                total=ungrouped_total,
                total_primary=0,
                total_utility=0,
                callers_suppressed=True,
            )

    base_join = select(Function, ViewNode.visible).where(
        this_side == function_id, Edge.kind == "call"
    )
    base_join = base_join.join(Edge, Function.id == other_side).outerjoin(
        ViewNode, and_(ViewNode.function_id == Function.id, ViewNode.view_id == view_id)
    )

    filter_clause = None
    if filter_text:
        like = f"%{filter_text}%"
        address_text = filter_text.strip()
        if address_text.lower().startswith("0x"):
            address_text = address_text[2:]
        filter_clause = or_(
            Function.name_ghidra.collate("NOCASE").like(like),
            Function.name_llm.collate("NOCASE").like(like),
            Function.name_analyst.collate("NOCASE").like(like),
            Function.summary_short.collate("NOCASE").like(like),
            cast(Function.address, String).like(like),
            func.printf("%X", Function.address).like(f"%{address_text.upper()}%"),
        )

    async def _group_total(is_utility_group: bool) -> int:
        stmt = base_join.where(Function.is_utility_effective.is_(is_utility_group))
        result = await session.execute(select(func.count()).select_from(stmt.subquery()))
        return result.scalar_one()

    total_primary = await _group_total(False)
    total_utility = await _group_total(True)

    group_stmt = base_join.where(Function.is_utility_effective.is_(group == "utility"))
    if filter_clause is not None:
        group_stmt = group_stmt.where(filter_clause)

    total = (
        await session.execute(select(func.count()).select_from(group_stmt.subquery()))
    ).scalar_one()

    if sort == "callOrder":
        if direction != "callees":
            raise ValueError("callOrder sorting is only defined for callees")
        # Legacy/schema-v1 edges have no static call-site order. Keep them
        # after known orders in both directions, then make pagination stable.
        order_by = [
            Edge.callee_order.is_(None).asc(),
            Edge.callee_order.desc() if order == "desc" else Edge.callee_order.asc(),
            Function.id.asc(),
        ]
    else:
        sort_expr = _SORT_EXPRESSIONS[sort]
        order_by = [sort_expr.desc() if order == "desc" else sort_expr.asc(), Function.id.asc()]
    page_stmt = (
        group_stmt.order_by(Function.is_utility_effective.asc(), *order_by)
        .limit(limit)
        .offset(offset)
    )
    page_rows = (await session.execute(page_stmt)).all()

    rows = [
        NeighbourRow(
            function=fn,
            on_canvas=bool(visible),
            is_self=fn.id == function_id,
        )
        for fn, visible in page_rows
    ]

    return NeighbourQueryResult(
        rows=rows,
        total=total,
        total_primary=total_primary,
        total_utility=total_utility,
        callers_suppressed=False,
    )
