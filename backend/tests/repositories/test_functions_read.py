"""I3: read repository methods — get-by-id, search, by-address, entry points."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Function
from graphrev.repositories.binaries import get_or_create_binary
from graphrev.repositories.functions import (
    get_function_by_id,
    list_entry_points,
    resolve_function_by_address,
    search_functions,
)


async def _make_function(
    session: AsyncSession,
    *,
    binary_id: int,
    address: int,
    name_ghidra: str = "fn",
    name_analyst: str | None = None,
    notes: str = "",
    fan_out: int = 0,
    is_entry_point: bool = False,
) -> Function:
    now = utc_now_iso()
    fn = Function(
        binary_id=binary_id,
        address=address,
        name_ghidra=name_ghidra,
        name_analyst=name_analyst,
        notes=notes,
        fan_out=fan_out,
        is_entry_point=is_entry_point,
        created_at=now,
        updated_at=now,
    )
    session.add(fn)
    await session.flush()
    return fn


@pytest.mark.asyncio
async def test_get_function_by_id_returns_none_when_missing(session: AsyncSession) -> None:
    assert await get_function_by_id(session, 999) is None


@pytest.mark.asyncio
async def test_get_function_by_id_returns_the_row(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    fn = await _make_function(session, binary_id=binary.id, address=0x1000, name_ghidra="main")
    await session.commit()
    fetched = await get_function_by_id(session, fn.id)
    assert fetched is not None
    assert fetched.name_ghidra == "main"


@pytest.mark.asyncio
async def test_search_functions_matches_name_ghidra_case_insensitively(
    session: AsyncSession,
) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await _make_function(session, binary_id=binary.id, address=0x1000, name_ghidra="parse_config")
    await _make_function(session, binary_id=binary.id, address=0x1010, name_ghidra="other_fn")
    await session.commit()

    rows, total = await search_functions(
        session, binary_id=binary.id, query="PARSE", limit=50, offset=0
    )
    assert total == 1
    assert rows[0].name_ghidra == "parse_config"


@pytest.mark.asyncio
async def test_search_functions_matches_name_analyst_and_notes(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await _make_function(
        session,
        binary_id=binary.id,
        address=0x1000,
        name_ghidra="FUN_00401000",
        name_analyst="my_renamed_fn",
    )
    await _make_function(
        session,
        binary_id=binary.id,
        address=0x1010,
        name_ghidra="FUN_00401010",
        notes="contains a secret keyword",
    )
    await _make_function(session, binary_id=binary.id, address=0x1020, name_ghidra="unrelated")
    await session.commit()

    by_analyst, total1 = await search_functions(
        session, binary_id=binary.id, query="renamed", limit=50, offset=0
    )
    assert total1 == 1
    assert by_analyst[0].name_ghidra == "FUN_00401000"

    by_notes, total2 = await search_functions(
        session, binary_id=binary.id, query="secret", limit=50, offset=0
    )
    assert total2 == 1
    assert by_notes[0].name_ghidra == "FUN_00401010"


@pytest.mark.asyncio
async def test_search_functions_matches_address_decimal_and_hex(
    session: AsyncSession,
) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await _make_function(session, binary_id=binary.id, address=0x401000, name_ghidra="fn_a")
    await _make_function(session, binary_id=binary.id, address=0x401010, name_ghidra="fn_b")
    await session.commit()

    by_decimal, total1 = await search_functions(
        session, binary_id=binary.id, query=str(0x401000), limit=50, offset=0
    )
    assert total1 == 1
    assert by_decimal[0].name_ghidra == "fn_a"

    by_hex, total2 = await search_functions(
        session, binary_id=binary.id, query="0x401010", limit=50, offset=0
    )
    assert total2 == 1
    assert by_hex[0].name_ghidra == "fn_b"


@pytest.mark.asyncio
async def test_search_functions_paginates_and_reports_total(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    for i in range(5):
        await _make_function(
            session, binary_id=binary.id, address=0x1000 + i, name_ghidra=f"util_fn_{i}"
        )
    await session.commit()

    page1, total = await search_functions(
        session, binary_id=binary.id, query=None, limit=2, offset=0
    )
    page2, _ = await search_functions(session, binary_id=binary.id, query=None, limit=2, offset=2)
    assert total == 5
    assert len(page1) == 2
    assert len(page2) == 2
    assert {f.id for f in page1}.isdisjoint({f.id for f in page2})


@pytest.mark.asyncio
async def test_search_functions_scoped_to_binary(session: AsyncSession) -> None:
    b1, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    b2, _ = await get_or_create_binary(session, name="libparse.dll", version="1.0")
    await _make_function(session, binary_id=b1.id, address=0x1000, name_ghidra="parse_a")
    await _make_function(session, binary_id=b2.id, address=0x2000, name_ghidra="parse_b")
    await session.commit()

    rows, total = await search_functions(
        session, binary_id=b1.id, query="parse", limit=50, offset=0
    )
    assert total == 1
    assert rows[0].name_ghidra == "parse_a"


@pytest.mark.asyncio
async def test_resolve_function_by_address_exact_match(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await _make_function(session, binary_id=binary.id, address=0x1000, name_ghidra="fn_a")
    await session.commit()

    resolved = await resolve_function_by_address(session, binary_id=binary.id, address=0x1000)
    assert resolved is not None
    assert resolved.name_ghidra == "fn_a"


@pytest.mark.asyncio
async def test_resolve_function_by_address_mid_range_resolves_to_container(
    session: AsyncSession,
) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await _make_function(session, binary_id=binary.id, address=0x1000, name_ghidra="fn_a")
    await _make_function(session, binary_id=binary.id, address=0x2000, name_ghidra="fn_b")
    await session.commit()

    resolved = await resolve_function_by_address(session, binary_id=binary.id, address=0x1050)
    assert resolved is not None
    assert resolved.name_ghidra == "fn_a"


@pytest.mark.asyncio
async def test_resolve_function_by_address_before_all_functions_returns_none(
    session: AsyncSession,
) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await _make_function(session, binary_id=binary.id, address=0x1000, name_ghidra="fn_a")
    await session.commit()

    resolved = await resolve_function_by_address(session, binary_id=binary.id, address=0x500)
    assert resolved is None


@pytest.mark.asyncio
async def test_list_entry_points_only_returns_flagged_rows_ordered_by_fan_out(
    session: AsyncSession,
) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    await _make_function(
        session,
        binary_id=binary.id,
        address=0x1000,
        name_ghidra="main",
        fan_out=12,
        is_entry_point=True,
    )
    await _make_function(
        session,
        binary_id=binary.id,
        address=0x1010,
        name_ghidra="alt_entry",
        fan_out=20,
        is_entry_point=True,
    )
    await _make_function(
        session,
        binary_id=binary.id,
        address=0x1020,
        name_ghidra="not_an_entry",
        fan_out=999,
        is_entry_point=False,
    )
    await session.commit()

    entry_points = await list_entry_points(session, binary_id=binary.id, limit=5)
    assert [f.name_ghidra for f in entry_points] == ["alt_entry", "main"]


@pytest.mark.asyncio
async def test_list_entry_points_respects_limit(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="acme.exe", version="1.0")
    for i in range(8):
        await _make_function(
            session,
            binary_id=binary.id,
            address=0x1000 + i,
            name_ghidra=f"entry_{i}",
            fan_out=i,
            is_entry_point=True,
        )
    await session.commit()

    entry_points = await list_entry_points(session, binary_id=binary.id, limit=5)
    assert len(entry_points) == 5
