"""Agent-facing MCP service behavior."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.core.errors import AppError, ErrorCode
from graphrev.db.models import Edge, Function
from graphrev.repositories.binaries import get_or_create_binary
from graphrev.services.mcp_service import get_mcp_function, set_mcp_function_info


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

    assert detail.assembly == "2000: RET"
    assert detail.code_c == "return 0;"
    assert [fn.display_name for fn in detail.callers] == ["caller"]
    assert [fn.display_name for fn in detail.callees] == ["first", "second"]
    assert [fn.callee_order for fn in detail.callees] == [0, 1]


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
