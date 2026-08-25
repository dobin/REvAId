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
from graphrev.db.models import Function
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
        schema_version=1,
        binary=GhidraExportBinary(name="sample.exe", version="1.0", source_path="/tmp/sample.exe"),
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
            GhidraExportEdge(caller_address=0x401000, callee_address=0x401100),
            # A cross-module edge whose target is not in `functions` -> B17 placeholder.
            GhidraExportEdge(
                caller_address=0x401000, callee_address=0x7FF00000, callee_module="ntdll.dll"
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
    kinds = sorted(r.kind for r in rows)
    # 3 real (normal/normal/import) + 1 placeholder.
    assert "placeholder" in kinds
    assert len([k for k in kinds if k != "placeholder"]) == 3


@pytest.mark.asyncio
async def test_reimport_is_idempotent_and_preserves_analyst_fields(
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

    second = await binary_service.import_ghidra_export(session_factory, settings, _document())

    assert second.binary_id == first.binary_id
    assert second.functions_inserted == 0
    assert second.functions_updated > 0

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
async def test_import_rejects_unsupported_schema_version(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    doc = _document()
    doc.schema_version = 999

    with pytest.raises(AppError) as excinfo:
        await binary_service.import_ghidra_export(session_factory, settings, doc)
    assert excinfo.value.code == ErrorCode.VALIDATION_ERROR
