"""PE data extraction: assembly parsing, classification, persistence, MCP tools."""

from __future__ import annotations

from pathlib import Path

import pytest
from pe_fixture import (
    BSS_RVA,
    GLOBAL_RVA,
    IMAGE_BASE,
    POINTER_RVA,
    STRING_RVA,
    WSTRING_RVA,
    build_pe,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revaid.core.config import Settings
from revaid.db.models import DataItem, DataRef, Function
from revaid.ingestion.pe_data.asm_refs import iter_asm_literals
from revaid.ingestion.pe_data.enrich import enrich_binary_with_pe_data
from revaid.ingestion.pe_data.pe_image import PeImage
from revaid.repositories.binaries import delete_binary, get_or_create_binary
from revaid.services.mcp_service import (
    find_mcp_functions_by_data,
    find_mcp_related_by_data,
    get_mcp_data_item,
    get_mcp_function_data,
    search_mcp_data,
)
from revaid_contracts.clock import utc_now_iso
from revaid_contracts.http_errors import AppError


def _va(rva: int) -> int:
    return IMAGE_BASE + rva


def test_asm_literals_from_real_export_lines() -> None:
    asm = (
        "140001000  PUSH RBX\n"
        "1400010e7  MOV RAX,qword ptr [0x140027000]\n"
        "1400010fe  LEA RCX,[0x140022720]\n"
        "14000110a  XOR EAX,EAX\n"
        "1400011de  CALL qword ptr [0x14001a038]\n"
        "140001103  MOV EAX,0x10\n"
    )
    literals = [(lit.instruction_address, lit.value) for lit in iter_asm_literals(asm)]
    assert literals == [
        (0x1400010E7, 0x140027000),
        (0x1400010FE, 0x140022720),
        (0x1400011DE, 0x14001A038),
    ]


def test_string_and_byte_limits_cut_off(tmp_path: Path) -> None:
    from revaid.ingestion.pe_data.classify import classify_data

    class _Fake:
        image_base = 0x1000
        size_of_image = 0x10000
        pointer_size = 8
        import_slots: dict[int, str] = {}  # noqa: RUF012
        relocation_rvas: set[int] = set()  # noqa: RUF012

        def __init__(self, data: bytes) -> None:
            self._data = data

        def section_at(self, rva: int) -> None:
            return None

        def read(self, rva: int, length: int) -> bytes:
            return self._data[:length]

    long_ascii = classify_data(_Fake(b"A" * 5000), 0, preview_bytes=128, max_string_bytes=1024)
    assert long_ascii.kind == "string"
    assert long_ascii.value_text == "A" * 1024

    wide = classify_data(
        _Fake("B".encode("utf-16le") * 3000), 0, preview_bytes=128, max_string_bytes=1024
    )
    assert wide.kind == "wstring"
    assert wide.value_text == "B" * 512  # 1024 bytes

    blob = classify_data(_Fake(bytes(range(1, 200))), 0, preview_bytes=128, max_string_bytes=1024)
    assert blob.kind == "bytes"
    assert blob.preview_hex is not None
    assert len(blob.preview_hex) == 128 * 2


def test_pe_image_sections(tmp_path: Path) -> None:
    image = PeImage(build_pe(tmp_path / "t.exe"))
    assert image.image_base == IMAGE_BASE
    names = {s.name: s for s in image.sections}
    assert names[".text"].executable
    assert names[".data"].writable
    assert image.read(STRING_RVA, 5) == b"hello"
    assert image.read(BSS_RVA, 4) is None


async def _add_function(
    session: AsyncSession, binary_id: int, address: int, name: str, assembly: str
) -> Function:
    now = utc_now_iso()
    fn = Function(
        binary_id=binary_id,
        address=address,
        name=name,
        assembly=assembly,
        created_at=now,
        updated_at=now,
    )
    session.add(fn)
    await session.flush()
    return fn


async def _seed(
    session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> tuple[int, dict[str, int]]:
    binary, _ = await get_or_create_binary(
        session, name="pe.exe", version="1", analysis_image_base=IMAGE_BASE
    )
    text = _va(0x1000)
    a = await _add_function(
        session,
        binary.id,
        text,
        "func_a",
        f"{text:x}  LEA RCX,[{_va(STRING_RVA):#x}]\n"
        f"{text + 7:x}  LEA RDX,[{_va(WSTRING_RVA):#x}]\n"
        f"{text + 14:x}  MOV RAX,qword ptr [{_va(POINTER_RVA):#x}]\n"
        f"{text + 21:x}  MOV qword ptr [{_va(GLOBAL_RVA):#x}],RAX\n"
        f"{text + 28:x}  MOV EAX,dword ptr [{_va(BSS_RVA):#x}]\n"
        f"{text + 35:x}  MOV EAX,dword ptr [{_va(0x1000):#x}]\n",  # code, ignored
    )
    b = await _add_function(
        session,
        binary.id,
        text + 0x40,
        "func_b",
        f"{text + 0x40:x}  LEA RCX,[{_va(STRING_RVA):#x}]\n",
    )
    c = await _add_function(
        session,
        binary.id,
        text + 0x80,
        "func_c",
        f"{text + 0x80:x}  LEA RCX,[{_va(WSTRING_RVA):#x}]\n"
        f"{text + 0x87:x}  LEA RCX,[{_va(STRING_RVA):#x}]\n",
    )
    await session.commit()
    return binary.id, {"a": a.id, "b": b.id, "c": c.id}


@pytest.mark.asyncio
async def test_enrich_persists_items_and_refs(
    tmp_path: Path,
    settings: Settings,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    binary_id, ids = await _seed(session, session_factory)
    pe = build_pe(tmp_path / "t.exe")

    report = await enrich_binary_with_pe_data(
        session_factory, settings, binary_name="pe.exe", binary_version="1", pe_path=pe
    )
    assert report.warnings == []
    assert report.items_inserted == 5
    assert report.refs_inserted == 8

    items = {
        i.address: i
        for i in (
            await session.execute(select(DataItem).where(DataItem.binary_id == binary_id))
        ).scalars()
    }
    assert items[_va(STRING_RVA)].kind == "string"
    assert items[_va(STRING_RVA)].value_text == "hello world"
    assert items[_va(STRING_RVA)].section == ".rdata"
    assert items[_va(STRING_RVA)].ref_count == 3
    assert items[_va(WSTRING_RVA)].kind == "wstring"
    assert items[_va(WSTRING_RVA)].value_text == "wide text"
    pointer = items[_va(POINTER_RVA)]
    assert pointer.kind == "pointer"
    assert pointer.target_address == _va(STRING_RVA)
    assert pointer.value_text == "hello world"
    assert items[_va(GLOBAL_RVA)].kind == "bytes"
    assert items[_va(GLOBAL_RVA)].is_writable
    assert items[_va(BSS_RVA)].kind == "uninitialized"
    assert _va(0x1000) not in items

    # Idempotent re-run.
    again = await enrich_binary_with_pe_data(
        session_factory, settings, binary_name="pe.exe", binary_version="1", pe_path=pe
    )
    assert (again.items_inserted, again.refs_inserted) == (5, 8)

    # Cascade on delete.
    session.expire_all()
    binary, _ = await get_or_create_binary(session, name="pe.exe", version="1")
    await delete_binary(session, binary)
    await session.commit()
    assert await session.scalar(select(func.count()).select_from(DataItem)) == 0
    assert await session.scalar(select(func.count()).select_from(DataRef)) == 0
    assert ids  # silence unused


@pytest.mark.asyncio
async def test_non_pe_file_is_a_warning_not_an_error(
    tmp_path: Path,
    settings: Settings,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(session, session_factory)
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"MZ not really a pe")
    report = await enrich_binary_with_pe_data(
        session_factory, settings, binary_name="pe.exe", binary_version="1", pe_path=bad
    )
    assert report.items_inserted == 0
    assert len(report.warnings) == 1
    assert "skipped" in report.warnings[0]


@pytest.mark.asyncio
async def test_mcp_data_tools(
    tmp_path: Path,
    settings: Settings,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, ids = await _seed(session, session_factory)
    await enrich_binary_with_pe_data(
        session_factory,
        settings,
        binary_name="pe.exe",
        binary_version="1",
        pe_path=build_pe(tmp_path / "t.exe"),
    )
    session.expire_all()

    page = await search_mcp_data(
        session,
        binary_name="pe.exe",
        binary_version="1",
        query="hello",
        kind=None,
        section=None,
        min_refs=None,
        max_refs=None,
        sort="address",
        limit=10,
        offset=0,
        max_limit=200,
    )
    kinds = sorted(i.kind for i in page.items)
    assert kinds == ["pointer", "string"]  # pointer's target string also matches

    rare = await search_mcp_data(
        session,
        binary_name="pe.exe",
        binary_version="1",
        query=None,
        kind="wstring",
        section=".rdata",
        min_refs=None,
        max_refs=2,
        sort="refs_asc",
        limit=10,
        offset=0,
        max_limit=200,
    )
    assert [i.value_text for i in rare.items] == ["wide text"]

    # Raw bytes are searchable by hex, in several spellings.
    for spelling in ("01 02 03 04", "0x01020304", "\\x01\\x02\\x03\\x04"):
        by_bytes = await search_mcp_data(
            session,
            binary_name="pe.exe",
            binary_version="1",
            query=spelling,
            kind="bytes",
            section=None,
            min_refs=None,
            max_refs=None,
            sort="address",
            limit=10,
            offset=0,
            max_limit=200,
        )
        assert [i.address for i in by_bytes.items] == [_va(GLOBAL_RVA)], spelling

    detail = await get_mcp_data_item(
        session,
        binary_name="pe.exe",
        binary_version="1",
        data_item_id=None,
        address=hex(_va(STRING_RVA)),
        limit=10,
        offset=0,
        max_limit=200,
    )
    assert detail.total_references == 3
    assert {r.function_display_name for r in detail.references} == {"func_a", "func_b", "func_c"}

    fdata = await get_mcp_function_data(
        session,
        binary_name="pe.exe",
        binary_version="1",
        function_id=ids["b"],
        address=None,
        name=None,
        limit=10,
        offset=0,
        max_limit=200,
    )
    assert [r.item.value_text for r in fdata.references] == ["hello world"]

    by_data = await find_mcp_functions_by_data(
        session,
        binary_name="pe.exe",
        binary_version="1",
        query="wide",
        kind=None,
        section=None,
        min_refs=None,
        max_refs=None,
        limit=10,
        offset=0,
        max_limit=200,
    )
    assert {f.function.name for f in by_data.functions} == {"func_a", "func_c"}

    related = await find_mcp_related_by_data(
        session,
        binary_name="pe.exe",
        binary_version="1",
        function_id=ids["a"],
        address=None,
        name=None,
        max_item_ref_count=3,
        limit=10,
    )
    assert related.related[0].function.name == "func_c"  # shares two items

    with pytest.raises(AppError):
        await get_mcp_data_item(
            session,
            binary_name="pe.exe",
            binary_version="1",
            data_item_id=None,
            address=None,
            limit=10,
            offset=0,
            max_limit=200,
        )
