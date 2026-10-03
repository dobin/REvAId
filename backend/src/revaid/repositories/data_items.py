"""PE data item / data reference repository.

Write side: :func:`replace_binary_data` (idempotent, whole-binary replacement).
Read side: queries used by the MCP data tools.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Select, String, cast, delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from revaid.db.models import DataItem, DataRef, Function
from revaid_contracts.clock import utc_now_iso

_INSERT_CHUNK = 5000


@dataclass(frozen=True, slots=True)
class DataItemValues:
    address: int
    rva: int
    section: str
    kind: str
    size: int
    value_text: str | None
    target_address: int | None
    preview_hex: str | None
    is_writable: bool


@dataclass(frozen=True, slots=True)
class DataRefValues:
    function_id: int
    item_address: int
    instruction_address: int
    instruction_text: str


@dataclass(frozen=True, slots=True)
class DataFunctionRef:
    """A reference joined with the function that makes it."""

    ref: DataRef
    function: Function


@dataclass(frozen=True, slots=True)
class FunctionDataRef:
    """A reference joined with the referenced data item."""

    ref: DataRef
    item: DataItem


@dataclass(frozen=True, slots=True)
class RelatedByData:
    function: Function
    shared_items: list[DataItem]
    score: float


async def replace_binary_data(
    session: AsyncSession,
    *,
    binary_id: int,
    items: Sequence[DataItemValues],
    refs: Sequence[DataRefValues],
) -> tuple[int, int]:
    """Replace all data items/refs of a binary. Returns ``(items, refs)`` inserted."""
    await session.execute(delete(DataRef).where(DataRef.binary_id == binary_id))
    await session.execute(delete(DataItem).where(DataItem.binary_id == binary_id))
    if not items:
        return 0, 0

    now = utc_now_iso()
    ref_counts: dict[int, int] = {}
    for r in refs:
        ref_counts[r.item_address] = ref_counts.get(r.item_address, 0) + 1
    item_rows = [
        {
            "binary_id": binary_id,
            "address": i.address,
            "rva": i.rva,
            "section": i.section,
            "kind": i.kind,
            "size": i.size,
            "value_text": i.value_text,
            "target_address": i.target_address,
            "preview_hex": i.preview_hex,
            "is_writable": i.is_writable,
            "ref_count": ref_counts.get(i.address, 0),
            "created_at": now,
        }
        for i in items
    ]
    for start in range(0, len(item_rows), _INSERT_CHUNK):
        await session.execute(insert(DataItem), item_rows[start : start + _INSERT_CHUNK])
    rows = (
        await session.execute(
            select(DataItem.address, DataItem.id).where(DataItem.binary_id == binary_id)
        )
    ).all()
    item_ids = {address: item_id for address, item_id in rows}

    ref_rows = [
        {
            "binary_id": binary_id,
            "function_id": r.function_id,
            "data_item_id": item_ids[r.item_address],
            "instruction_address": r.instruction_address,
            "instruction_text": r.instruction_text,
            "source": "asm-parse",
        }
        for r in refs
        if r.item_address in item_ids
    ]
    for start in range(0, len(ref_rows), _INSERT_CHUNK):
        await session.execute(insert(DataRef), ref_rows[start : start + _INSERT_CHUNK])
    return len(items), len(ref_rows)


def _apply_item_filters(
    stmt: Select[tuple[DataItem]],
    *,
    binary_id: int,
    query: str | None,
    kind: str | None,
    section: str | None,
    min_refs: int | None,
    max_refs: int | None,
) -> Select[tuple[DataItem]]:
    stmt = stmt.where(DataItem.binary_id == binary_id)
    if query:
        needle = query.strip()
        hex_needle = needle.lower().removeprefix("0x")
        clauses = [
            DataItem.value_text.collate("NOCASE").contains(needle, autoescape=True),
            func.printf("%X", DataItem.address).contains(hex_needle.upper(), autoescape=True),
            cast(DataItem.address, String).contains(needle, autoescape=True),
        ]
        # Byte search over the stored (cut-off) hex preview: accepts
        # "de ad be ef", "0xdeadbeef" or "\xde\xad".
        byte_needle = re.sub(r"0x|\\x|[\s,]", "", needle.lower())
        if len(byte_needle) >= 2 and re.fullmatch(r"[0-9a-f]+", byte_needle):
            clauses.append(DataItem.preview_hex.contains(byte_needle, autoescape=True))
        stmt = stmt.where(or_(*clauses))
    if kind == "string":
        stmt = stmt.where(DataItem.kind.in_(("string", "wstring")))
    elif kind:
        stmt = stmt.where(DataItem.kind == kind)
    if section:
        stmt = stmt.where(DataItem.section.collate("NOCASE") == section)
    if min_refs is not None:
        stmt = stmt.where(DataItem.ref_count >= min_refs)
    if max_refs is not None:
        stmt = stmt.where(DataItem.ref_count <= max_refs)
    return stmt


async def search_data_items(
    session: AsyncSession,
    *,
    binary_id: int,
    query: str | None,
    kind: str | None,
    section: str | None,
    min_refs: int | None,
    max_refs: int | None,
    sort: str,
    limit: int,
    offset: int,
) -> tuple[list[DataItem], int]:
    base = _apply_item_filters(
        select(DataItem),
        binary_id=binary_id,
        query=query,
        kind=kind,
        section=section,
        min_refs=min_refs,
        max_refs=max_refs,
    )
    total = int(
        await session.scalar(select(func.count()).select_from(base.order_by(None).subquery())) or 0
    )
    if sort == "refs_asc":
        base = base.order_by(DataItem.ref_count.asc(), DataItem.address.asc())
    elif sort == "refs_desc":
        base = base.order_by(DataItem.ref_count.desc(), DataItem.address.asc())
    else:
        base = base.order_by(DataItem.address.asc())
    rows = (await session.execute(base.limit(limit).offset(offset))).scalars()
    return list(rows), total


async def get_data_item_by_id(
    session: AsyncSession, *, binary_id: int, data_item_id: int
) -> DataItem | None:
    item = await session.get(DataItem, data_item_id)
    if item is None or item.binary_id != binary_id:
        return None
    return item


async def get_data_item_by_address(
    session: AsyncSession, *, binary_id: int, address: int
) -> DataItem | None:
    result: DataItem | None = await session.scalar(
        select(DataItem).where(DataItem.binary_id == binary_id, DataItem.address == address)
    )
    return result


async def update_data_item_summary(
    session: AsyncSession,
    *,
    data_item_id: int,
    summary_llm: str | None,
) -> DataItem | None:
    """Set or clear the agent-authored summary without committing."""
    item = await session.get(DataItem, data_item_id)
    if item is None:
        return None
    await session.execute(
        update(DataItem).where(DataItem.id == data_item_id).values(summary_llm=summary_llm)
    )
    await session.flush()
    await session.refresh(item)
    return item


async def list_item_refs(
    session: AsyncSession, *, data_item_id: int, limit: int, offset: int
) -> tuple[list[DataFunctionRef], int]:
    total = int(
        await session.scalar(
            select(func.count()).select_from(DataRef).where(DataRef.data_item_id == data_item_id)
        )
        or 0
    )
    rows = (
        await session.execute(
            select(DataRef, Function)
            .join(Function, Function.id == DataRef.function_id)
            .where(DataRef.data_item_id == data_item_id)
            .order_by(Function.address, DataRef.instruction_address)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [DataFunctionRef(ref=r, function=f) for r, f in rows], total


async def list_function_refs(
    session: AsyncSession, *, function_id: int, limit: int, offset: int
) -> tuple[list[FunctionDataRef], int]:
    total = int(
        await session.scalar(
            select(func.count()).select_from(DataRef).where(DataRef.function_id == function_id)
        )
        or 0
    )
    rows = (
        await session.execute(
            select(DataRef, DataItem)
            .join(DataItem, DataItem.id == DataRef.data_item_id)
            .where(DataRef.function_id == function_id)
            .order_by(DataRef.instruction_address, DataItem.address)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [FunctionDataRef(ref=r, item=i) for r, i in rows], total


async def find_functions_by_matching_items(
    session: AsyncSession,
    *,
    binary_id: int,
    query: str | None,
    kind: str | None,
    section: str | None,
    min_refs: int | None,
    max_refs: int | None,
    limit: int,
    offset: int,
) -> tuple[list[tuple[Function, list[DataItem]]], int]:
    """Functions referencing any item that matches the item filters."""
    matching = _apply_item_filters(
        select(DataItem.id),
        binary_id=binary_id,
        query=query,
        kind=kind,
        section=section,
        min_refs=min_refs,
        max_refs=max_refs,
    )
    function_ids = select(DataRef.function_id).where(DataRef.data_item_id.in_(matching)).distinct()
    total = int(
        await session.scalar(
            select(func.count()).select_from(Function).where(Function.id.in_(function_ids))
        )
        or 0
    )
    functions = list(
        (
            await session.execute(
                select(Function)
                .where(Function.id.in_(function_ids))
                .order_by(Function.address)
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
    )
    if not functions:
        return [], total
    pairs = (
        await session.execute(
            select(DataRef.function_id, DataItem)
            .join(DataItem, DataItem.id == DataRef.data_item_id)
            .where(
                DataRef.function_id.in_([f.id for f in functions]),
                DataItem.id.in_(matching),
            )
            .distinct()
            .order_by(DataItem.address)
        )
    ).all()
    grouped: dict[int, list[DataItem]] = {f.id: [] for f in functions}
    for function_id, item in pairs:
        grouped[function_id].append(item)
    return [(f, grouped[f.id]) for f in functions], total


async def find_related_by_data(
    session: AsyncSession,
    *,
    binary_id: int,
    function_id: int,
    max_item_ref_count: int,
    limit: int,
) -> list[RelatedByData]:
    """Rank other functions by shared data items, rarer items weighing more.

    Score per shared item is ``1 / ref_count``; items referenced by more than
    ``max_item_ref_count`` functions (cookies, common globals) are ignored.
    """
    own = (
        select(DataRef.data_item_id)
        .join(DataItem, DataItem.id == DataRef.data_item_id)
        .where(
            DataRef.function_id == function_id,
            DataItem.binary_id == binary_id,
            DataItem.ref_count <= max_item_ref_count,
        )
        .distinct()
    )
    rows = (
        await session.execute(
            select(DataRef.function_id, DataItem)
            .join(DataItem, DataItem.id == DataRef.data_item_id)
            .where(DataRef.data_item_id.in_(own), DataRef.function_id != function_id)
            .distinct()
        )
    ).all()
    shared: dict[int, list[DataItem]] = {}
    for other_id, item in rows:
        shared.setdefault(other_id, []).append(item)
    scored = sorted(
        (
            (sum(1.0 / max(i.ref_count, 1) for i in items), other_id, items)
            for other_id, items in shared.items()
        ),
        key=lambda t: (-t[0], t[1]),
    )[:limit]
    if not scored:
        return []
    functions = {
        f.id: f
        for f in (
            await session.execute(select(Function).where(Function.id.in_([s[1] for s in scored])))
        ).scalars()
    }
    return [
        RelatedByData(
            function=functions[other_id],
            shared_items=sorted(items, key=lambda i: i.address),
            score=score,
        )
        for score, other_id, items in scored
    ]
