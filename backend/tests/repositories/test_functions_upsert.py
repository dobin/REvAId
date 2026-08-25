"""A3: the highest-value test in the suite — idempotent UPSERT preserves
LLM-owned and analyst-owned fields across re-ingestion."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import Binary, Function
from graphrev.repositories.functions import (
    upsert_function,
)


async def _make_binary(session: AsyncSession, name: str = "acme.exe") -> Binary:
    now = utc_now_iso()
    binary = Binary(name=name, version="1.0", created_at=now, updated_at=now)
    session.add(binary)
    await session.flush()
    return binary


@pytest.mark.asyncio
async def test_upsert_function_inserts_new_row(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    function_id, created = await upsert_function(
        session,
        binary_id=binary.id,
        address=0x1000,
        name_ghidra="main",
        code_c="int main() { return 0; }",
    )
    await session.commit()

    assert created is True
    fn = await session.get(Function, function_id)
    assert fn is not None
    assert fn.name_ghidra == "main"
    assert fn.code_c == "int main() { return 0; }"


@pytest.mark.asyncio
async def test_upsert_function_is_idempotent_on_second_call(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    id1, created1 = await upsert_function(
        session, binary_id=binary.id, address=0x1000, name_ghidra="main"
    )
    await session.commit()
    id2, created2 = await upsert_function(
        session, binary_id=binary.id, address=0x1000, name_ghidra="main"
    )
    await session.commit()

    assert id1 == id2
    assert created1 is True
    assert created2 is False


@pytest.mark.asyncio
async def test_reingest_preserves_llm_and_analyst_fields(session: AsyncSession) -> None:
    """The A3 behavioural guard: re-running ingestion must never clobber
    summary_*, name_analyst, notes, or utility_override — even when
    ground-truth fields (name_ghidra, code_c, kind) genuinely change."""
    binary = await _make_binary(session)
    function_id, _ = await upsert_function(
        session, binary_id=binary.id, address=0x1000, name_ghidra="FUN_00001000"
    )
    await session.commit()

    fn = await session.get(Function, function_id)
    assert fn is not None
    fn.summary_short = "Parses the on-disk configuration."
    fn.summary_status = "ready"
    fn.summary_adapter = "litellm"  # I13/AM4: adapter provenance is LLM-owned
    fn.name_analyst = "parse_config"
    fn.notes = "Confirmed this handles the v2 format only."
    fn.utility_override = "never"
    await session.commit()

    # Re-ingestion: ground truth changed (Ghidra now has a symbolic name and
    # different decompiled code), as if a rebuild or improved analysis ran.
    same_id, created = await upsert_function(
        session,
        binary_id=binary.id,
        address=0x1000,
        name_ghidra="parse_config_v2",
        code_c="int parse_config_v2(char *path) { return 0; }",
        kind="normal",
    )
    await session.commit()

    assert same_id == function_id
    assert created is False

    await session.refresh(fn)
    refreshed = fn
    # Ground truth updated.
    assert refreshed.name_ghidra == "parse_config_v2"
    assert refreshed.code_c == "int parse_config_v2(char *path) { return 0; }"
    # LLM- and analyst-owned fields untouched (A3).
    assert refreshed.summary_short == "Parses the on-disk configuration."
    assert refreshed.summary_status == "ready"
    assert refreshed.summary_adapter == "litellm"
    assert refreshed.name_analyst == "parse_config"
    assert refreshed.notes == "Confirmed this handles the v2 format only."
    assert refreshed.utility_override == "never"


@pytest.mark.asyncio
async def test_upsert_function_placeholder_kind_has_no_code(session: AsyncSession) -> None:
    binary = await _make_binary(session)
    function_id, _ = await upsert_function(
        session,
        binary_id=binary.id,
        address=0x10005000,
        name_ghidra="libparse.dll!FUN_10005000",
        kind="placeholder",
        placeholder_module="libparse.dll",
    )
    await session.commit()

    fn = await session.get(Function, function_id)
    assert fn is not None
    assert fn.kind == "placeholder"
    assert fn.assembly is None
    assert fn.code_c is None
    assert fn.placeholder_module == "libparse.dll"


@pytest.mark.asyncio
async def test_placeholder_upgraded_in_place_by_later_ingestion(session: AsyncSession) -> None:
    """B17: a later full ingestion of the module upgrades the placeholder row
    in place, preserving its id, while clearing placeholder-specific fields."""
    binary = await _make_binary(session)
    placeholder_id, _ = await upsert_function(
        session,
        binary_id=binary.id,
        address=0x10005000,
        name_ghidra="libparse.dll!FUN_10005000",
        kind="placeholder",
        placeholder_module="libparse.dll",
    )
    await session.commit()
    placeholder = await session.get(Function, placeholder_id)
    assert placeholder is not None

    upgraded_id, created = await upsert_function(
        session,
        binary_id=binary.id,
        address=0x10005000,
        name_ghidra="parse_section",
        code_c="int parse_section(void) { return 1; }",
        kind="normal",
        placeholder_module=None,
    )
    await session.commit()

    assert upgraded_id == placeholder_id
    assert created is False

    await session.refresh(placeholder)
    assert placeholder.kind == "normal"
    assert placeholder.name_ghidra == "parse_section"
    assert placeholder.code_c == "int parse_section(void) { return 1; }"
    assert placeholder.placeholder_module is None
