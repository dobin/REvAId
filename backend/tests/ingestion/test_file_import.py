"""File-based Ghidra JSON import (I12): `FileGhidraAdapter` + the
`binary_service.import_ghidra_export` use case.

Mirrors the invariants asserted for the mock adapter in `test_pipeline.py`
(idempotency A3, placeholder materialisation B17) but drives them through a
parsed `GhidraExportDocument`, the shape produced by
`tools/ghidra/GraphRevExport.java`."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graphrev.core.config import Settings
from graphrev.core.errors import AppError, ErrorCode
from graphrev.db.models import Binary, Edge, Function
from graphrev.schemas.ingest import (
    GhidraExportBinary,
    GhidraExportDocument,
    GhidraExportEdge,
    GhidraExportFunction,
    GhidraExportParam,
)
from graphrev.services import binary_service


def _document() -> GhidraExportDocument:
    return GhidraExportDocument(
        schema_version=2,
        binary=GhidraExportBinary(
            name="sample.exe",
            version="1.0",
            source_path="/tmp/sample.exe",
            analysis_image_base=0x400000,
            sha256="a" * 64,
        ),
        functions=[
            GhidraExportFunction(
                address=0x401000,
                name="main",
                parameters=[GhidraExportParam(ordinal=0, name="argc", type="int")],
                signature="int main(int argc)",
                assembly="00401000  PUSH RBP",
                code_c="int main(int argc){return 0;}",
                kind="normal",
                is_entry_point=True,
            ),
            GhidraExportFunction(
                address=0x401100,
                name="helper",
                parameters=[],
                signature="void helper(void)",
                assembly="00401100  RET",
                code_c="void helper(void){}",
                kind="normal",
            ),
            GhidraExportFunction(
                address=0x401200,
                name="imp_strlen",
                parameters=[],
                signature=None,
                assembly=None,
                code_c=None,
                kind="import",
            ),
        ],
        edges=[
            GhidraExportEdge(caller_address=0x401000, callee_address=0x401100, callee_order=0),
            # A cross-module edge whose target is not in `functions` -> B17 placeholder.
            GhidraExportEdge(
                caller_address=0x401000,
                callee_address=0x7FF00000,
                callee_module="ntdll.dll",
                callee_order=1,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_import_creates_binary_with_functions_and_placeholder(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    result = await binary_service.import_ghidra_export(session_factory, settings, _document())

    assert result.name == "sample.exe"
    assert result.version == "1.0"
    # 3 real functions inserted.
    assert result.functions_inserted == 3
    assert result.functions_updated == 0
    # One cross-module edge materialised a placeholder (B17).
    assert result.placeholders_created == 1

    async with session_factory() as session:
        rows = (
            (await session.execute(select(Function).where(Function.binary_id == result.binary_id)))
            .scalars()
            .all()
        )
        binary = await session.get(Binary, result.binary_id)
        edge_orders = (
            (
                await session.execute(
                    select(Edge.callee_order)
                    .where(Edge.binary_id == result.binary_id)
                    .order_by(Edge.callee_order)
                )
            )
            .scalars()
            .all()
        )
    kinds = sorted(r.kind for r in rows)
    # 3 real (normal/normal/import) + 1 placeholder.
    assert "placeholder" in kinds
    assert len([k for k in kinds if k != "placeholder"]) == 3

    assert binary is not None
    assert binary.analysis_image_base == 0x400000
    assert binary.sha256 == "a" * 64
    assert edge_orders == [0, 1]


@pytest.mark.asyncio
async def test_import_legacy_document_leaves_analysis_image_base_null(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    doc = _document()
    doc.binary.analysis_image_base = None
    result = await binary_service.import_ghidra_export(session_factory, settings, doc)

    async with session_factory() as session:
        binary = await session.get(Binary, result.binary_id)
    assert binary is not None
    assert binary.analysis_image_base is None


@pytest.mark.asyncio
async def test_import_schema_v1_document_leaves_callee_order_unknown(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    doc = _document()
    doc.schema_version = 1
    for edge in doc.edges:
        edge.callee_order = None
    result = await binary_service.import_ghidra_export(session_factory, settings, doc)

    async with session_factory() as session:
        orders = (
            (
                await session.execute(
                    select(Edge.callee_order).where(Edge.binary_id == result.binary_id)
                )
            )
            .scalars()
            .all()
        )
    assert orders == [None, None]


@pytest.mark.asyncio
async def test_import_kuna_schema_v4_document_preserves_edge_kinds(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    doc = _document()
    doc.schema_version = 4
    doc.functions.append(
        GhidraExportFunction(
            address=0x401300,
            name="import_slot",
            kind="data",
        )
    )
    doc.edges[0].kind = "jump"
    doc.edges[1].kind = "data"

    result = await binary_service.import_ghidra_export(session_factory, settings, doc)

    async with session_factory() as session:
        edge_kinds = (await session.execute(select(Edge.kind).order_by(Edge.id))).scalars().all()
        data_row = (
            await session.execute(
                select(Function).where(
                    Function.binary_id == result.binary_id, Function.address == 0x401300
                )
            )
        ).scalar_one()
    assert edge_kinds == ["jump", "data"]
    assert data_row.kind == "external"
    assert data_row.code_c is None


@pytest.mark.asyncio
async def test_reimport_with_same_hash_is_rejected(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    first = await binary_service.import_ghidra_export(session_factory, settings, _document())

    # Analyst edits a function (owned columns must survive re-ingestion, A3).
    async with session_factory() as session:
        fn = (
            await session.execute(
                select(Function).where(
                    Function.binary_id == first.binary_id, Function.address == 0x401000
                )
            )
        ).scalar_one()
        fn.name_analyst = "entrypoint"
        fn.notes = "attacker reachable"
        await session.commit()

    renamed = _document()
    renamed.binary.name = "renamed.exe"
    with pytest.raises(AppError) as excinfo:
        await binary_service.import_ghidra_export(session_factory, settings, renamed)
    assert excinfo.value.code == ErrorCode.BINARY_ALREADY_EXISTS
    assert excinfo.value.details == {
        "match": "sha256",
        "existingBinaryId": first.binary_id,
        "existingName": "sample.exe",
        "existingVersion": "1.0",
    }

    async with session_factory() as session:
        fn = (
            await session.execute(
                select(Function).where(
                    Function.binary_id == first.binary_id, Function.address == 0x401000
                )
            )
        ).scalar_one()
    assert fn.name_analyst == "entrypoint"
    assert fn.notes == "attacker reachable"


@pytest.mark.asyncio
async def test_import_same_filename_with_different_hash_is_rejected(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    await binary_service.import_ghidra_export(session_factory, settings, _document())
    changed = _document()
    changed.binary.sha256 = "b" * 64

    with pytest.raises(AppError) as excinfo:
        await binary_service.import_ghidra_export(session_factory, settings, changed)
    assert excinfo.value.code == ErrorCode.BINARY_ALREADY_EXISTS
    assert excinfo.value.details["match"] == "filename"


@pytest.mark.asyncio
async def test_hashless_import_falls_back_to_filename_duplicate_check(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    first = _document()
    first.binary.sha256 = None
    await binary_service.import_ghidra_export(session_factory, settings, first)

    with pytest.raises(AppError) as excinfo:
        await binary_service.import_ghidra_export(session_factory, settings, first)
    assert excinfo.value.code == ErrorCode.BINARY_ALREADY_EXISTS
    assert excinfo.value.details["match"] == "filename"


def test_sha256_is_normalised_and_validated() -> None:
    doc = _document()
    doc.binary.sha256 = "A" * 64
    validated = GhidraExportDocument.model_validate(doc.model_dump())
    assert validated.binary.sha256 == "a" * 64

    payload = doc.model_dump()
    payload["binary"]["sha256"] = "not-a-digest"
    with pytest.raises(ValueError, match="64 hexadecimal"):
        GhidraExportDocument.model_validate(payload)


@pytest.mark.asyncio
async def test_import_rejects_unsupported_schema_version(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    doc = _document()
    doc.schema_version = 999

    with pytest.raises(AppError) as excinfo:
        await binary_service.import_ghidra_export(session_factory, settings, doc)
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR
