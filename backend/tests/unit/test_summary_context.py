"""C9: `build_summary_request` assembles a `SummaryRequest` from DB rows."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.core.errors import AppError
from graphrev.db.models import Binary, Edge, Function
from graphrev.summarization.context import build_summary_request


async def _make_binary(session: AsyncSession, name: str = "acme.exe") -> Binary:
    now = utc_now_iso()
    binary = Binary(name=name, version="1.0", created_at=now, updated_at=now)
    session.add(binary)
    await session.flush()
    return binary


async def _make_function(
    session: AsyncSession,
    binary: Binary,
    *,
    address: int,
    name: str,
    code_c: str | None = None,
    assembly: str | None = None,
    notes: str = "",
    name_analyst: str | None = None,
    summary_short: str | None = None,
) -> Function:
    now = utc_now_iso()
    fn = Function(
        binary_id=binary.id,
        address=address,
        name_ghidra=name,
        code_c=code_c,
        assembly=assembly,
        notes=notes,
        name_analyst=name_analyst,
        summary_short=summary_short,
        created_at=now,
        updated_at=now,
    )
    session.add(fn)
    await session.flush()
    return fn


async def test_build_summary_request_raises_for_missing_function(session: AsyncSession) -> None:
    with pytest.raises(AppError):
        await build_summary_request(session, function_id=99999)


async def test_build_summary_request_carries_binary_identity(session: AsyncSession) -> None:
    binary = await _make_binary(session, name="acme.exe")
    fn = await _make_function(session, binary, address=0x1000, name="do_thing")
    await session.commit()

    req = await build_summary_request(session, function_id=fn.id)

    assert req.binary_name == "acme.exe"
    assert req.binary_version == "1.0"
    assert req.name == "do_thing"
    assert req.address == 0x1000


async def test_build_summary_request_includes_callee_short_summaries(
    session: AsyncSession,
) -> None:
    binary = await _make_binary(session)
    caller = await _make_function(session, binary, address=0x1000, name="caller")
    callee = await _make_function(
        session, binary, address=0x2000, name="callee", summary_short="does a thing"
    )
    session.add(Edge(binary_id=binary.id, caller_id=caller.id, callee_id=callee.id, kind="call"))
    await session.commit()

    req = await build_summary_request(session, function_id=caller.id)

    assert req.callee_summaries == (("callee", "does a thing"),)


async def test_build_summary_request_excludes_callees_without_summary(
    session: AsyncSession,
) -> None:
    binary = await _make_binary(session)
    caller = await _make_function(session, binary, address=0x1000, name="caller")
    callee = await _make_function(session, binary, address=0x2000, name="callee")
    session.add(Edge(binary_id=binary.id, caller_id=caller.id, callee_id=callee.id, kind="call"))
    await session.commit()

    req = await build_summary_request(session, function_id=caller.id)

    assert req.callee_summaries == ()


async def test_build_summary_request_uses_analyst_name_for_callee_display(
    session: AsyncSession,
) -> None:
    binary = await _make_binary(session)
    caller = await _make_function(session, binary, address=0x1000, name="caller")
    callee = await _make_function(
        session,
        binary,
        address=0x2000,
        name="callee_ghidra",
        name_analyst="callee_renamed",
        summary_short="short",
    )
    session.add(Edge(binary_id=binary.id, caller_id=caller.id, callee_id=callee.id, kind="call"))
    await session.commit()

    req = await build_summary_request(session, function_id=caller.id)

    assert req.callee_summaries == (("callee_renamed", "short"),)
