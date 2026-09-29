"""Agent-facing MCP service behavior."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from revaid.core.config import get_settings
from revaid.db.models import Edge, Function
from revaid.repositories.binaries import get_or_create_binary
from revaid.services.mcp_service import get_mcp_function, set_mcp_function_info
from revaid_contracts.clock import utc_now_iso
from revaid_contracts.http_errors import AppError, ErrorCode


async def _function(session: AsyncSession, *, binary_id: int, address: int, name: str) -> Function:
    now = utc_now_iso()
    fn = Function(
        binary_id=binary_id,
        address=address,
        name=name,
        assembly=f"{address:x}: RET",
        code_c="return 0;",
        created_at=now,
        updated_at=now,
    )
    session.add(fn)
    await session.flush()
    return fn


@pytest.mark.asyncio
async def test_get_function_includes_callers_and_ordered_callees(
    session: AsyncSession,
) -> None:
    binary, _ = await get_or_create_binary(session, name="agent.exe", version="1")
    caller = await _function(session, binary_id=binary.id, address=0x1000, name="caller")
    target = await _function(session, binary_id=binary.id, address=0x2000, name="target")
    first = await _function(session, binary_id=binary.id, address=0x3000, name="first")
    second = await _function(session, binary_id=binary.id, address=0x4000, name="second")
    session.add_all(
        [
            Edge(binary_id=binary.id, caller_id=caller.id, callee_id=target.id),
            Edge(
                binary_id=binary.id,
                caller_id=target.id,
                callee_id=second.id,
                callee_order=1,
            ),
            Edge(
                binary_id=binary.id,
                caller_id=target.id,
                callee_id=first.id,
                callee_order=0,
            ),
        ]
    )
    await session.commit()

    detail = await get_mcp_function(
        session,
        binary_name="agent.exe",
        binary_version="1",
        address=target.address,
    )

    assert detail.assembly is None
    assert detail.code_c == "return 0;"
    assert [fn.display_name for fn in detail.callers] == ["caller"]
    assert [fn.display_name for fn in detail.callees] == ["first", "second"]
    assert [fn.callee_order for fn in detail.callees] == [0, 1]

    detail_with_assembly = await get_mcp_function(
        session,
        binary_name="agent.exe",
        binary_version="1",
        address=target.address,
        include_assembly=True,
    )
    assert detail_with_assembly.assembly == "2000: RET"

    detail_without_decompile = await get_mcp_function(
        session,
        binary_name="agent.exe",
        binary_version="1",
        address=target.address,
        include_decompile=False,
    )
    assert detail_without_decompile.code_c is None


@pytest.mark.asyncio
async def test_get_function_accepts_hex_address_string(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="agent.exe", version="1")
    fn = await _function(session, binary_id=binary.id, address=0x401000, name="main")
    await session.commit()

    detail = await get_mcp_function(
        session,
        binary_name=binary.name,
        binary_version=binary.version,
        address="0x00401000",
    )

    assert detail.id == fn.id
    assert detail.address == 0x401000


@pytest.mark.asyncio
async def test_get_function_rejects_invalid_address_string(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="agent.exe", version="1")

    with pytest.raises(AppError) as raised:
        await get_mcp_function(
            session,
            binary_name=binary.name,
            binary_version=binary.version,
            address="not-an-address",
        )

    assert raised.value.code == ErrorCode.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_set_function_info_updates_only_supplied_llm_fields(
    session: AsyncSession,
) -> None:
    binary, _ = await get_or_create_binary(session, name="agent.exe", version="")
    fn = await _function(session, binary_id=binary.id, address=0x1000, name="FUN_1000")
    fn.summary_long = "existing details"
    await session.commit()

    result = await set_mcp_function_info(
        session,
        binary_name="agent.exe",
        binary_version="",
        function_id=fn.id,
        name_llm="parse_packet",
        summary_short="Parses an incoming packet.",
    )

    await session.refresh(fn)
    assert result.updated_fields == ["name_llm", "summary_short"]
    assert fn.name_llm == "parse_packet"
    assert fn.summary_short == "Parses an incoming packet."
    assert fn.summary_long == "existing details"
    assert fn.summary_status == "ready"


@pytest.mark.asyncio
async def test_set_function_info_accepts_hex_address_string(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="agent.exe", version="")
    fn = await _function(session, binary_id=binary.id, address=0x401000, name="FUN_401000")
    await session.commit()

    result = await set_mcp_function_info(
        session,
        binary_name=binary.name,
        binary_version=binary.version,
        address="0x401000",
        name_llm="main",
    )

    await session.refresh(fn)
    assert result.id == fn.id
    assert fn.name_llm == "main"


@pytest.mark.asyncio
async def test_set_function_info_is_forbidden_in_public_mode(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binary, _ = await get_or_create_binary(session, name="agent.exe", version="")
    fn = await _function(session, binary_id=binary.id, address=0x1000, name="FUN_1000")
    await session.commit()

    monkeypatch.setenv("GRAPHREV_PUBLIC_MODE", "true")
    get_settings.cache_clear()
    try:
        with pytest.raises(AppError) as raised:
            await set_mcp_function_info(
                session,
                binary_name=binary.name,
                binary_version=binary.version,
                function_id=fn.id,
                name_llm="renamed_function",
            )
    finally:
        get_settings.cache_clear()

    await session.refresh(fn)
    assert raised.value.code == ErrorCode.PUBLIC_MODE_FORBIDDEN
    assert fn.name_llm is None


@pytest.mark.asyncio
async def test_function_id_must_belong_to_named_binary(session: AsyncSession) -> None:
    first, _ = await get_or_create_binary(session, name="first.exe", version="")
    second, _ = await get_or_create_binary(session, name="second.exe", version="")
    fn = await _function(session, binary_id=first.id, address=0x1000, name="main")
    await session.commit()

    with pytest.raises(AppError) as raised:
        await get_mcp_function(
            session,
            binary_name=second.name,
            binary_version=second.version,
            function_id=fn.id,
        )

    assert raised.value.code == ErrorCode.FUNCTION_NOT_FOUND


@pytest.mark.asyncio
async def test_ambiguous_exact_name_reports_candidates(session: AsyncSession) -> None:
    binary, _ = await get_or_create_binary(session, name="agent.exe", version="")
    await _function(session, binary_id=binary.id, address=0x1000, name="duplicate")
    await _function(session, binary_id=binary.id, address=0x2000, name="duplicate")
    await session.commit()

    with pytest.raises(AppError) as raised:
        await get_mcp_function(
            session,
            binary_name=binary.name,
            binary_version=binary.version,
            name="duplicate",
        )

    assert raised.value.code == ErrorCode.VALIDATION_ERROR
    assert raised.value.details is not None
    assert len(raised.value.details["matches"]) == 2
