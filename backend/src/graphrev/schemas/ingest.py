"""Ghidra JSON-export import DTOs (I12 — file-based ingestion).

The wire shape mirrors the JSON produced by ``tools/ghidra/GraphRevExport.java``
(schema v1). These DTOs are the *only* validation boundary for an uploaded
export — everything past :class:`GhidraExportDocument` is trusted, already-typed
data fed into the ingestion pipeline via
:class:`graphrev.adapters.ghidra.file.FileGhidraAdapter`.

Field names are ``camelCase`` on the wire (matching the exporter and the rest
of the API, TAD §4) and ``snake_case`` in Python via :class:`ApiModel`.
"""

from __future__ import annotations

from pydantic import Field

from graphrev.db.enums import FunctionKind
from graphrev.schemas.common import ApiModel

#: The only export schema version this build understands. The exporter writes
#: ``schemaVersion: 1``; a future bump gates here rather than silently
#: mis-parsing (see ``tools/ghidra/README.md``).
SUPPORTED_EXPORT_SCHEMA_VERSION = 1


class GhidraExportParam(ApiModel):
    """One decompiled parameter (maps to ``RawParam``)."""

    ordinal: int
    name: str
    type: str


class GhidraExportFunction(ApiModel):
    """One exported function (maps to ``RawFunction``).

    ``kind`` is one of the four *observable* kinds the exporter emits
    (``normal``/``import``/``thunk``/``external``); ``placeholder`` is never
    supplied by an adapter — it is materialised by ingestion from unresolved
    cross-module edges (B17).
    """

    address: int
    name: str
    parameters: list[GhidraExportParam] = Field(default_factory=list)
    signature: str | None = None
    assembly: str | None = None
    code_c: str | None = None
    kind: FunctionKind = "normal"
    has_indirect_calls: bool = False
    is_entry_point: bool = False


class GhidraExportEdge(ApiModel):
    """One caller -> callee edge (maps to ``RawEdge``).

    ``callee_module`` is set when the callee lives outside this binary; that
    is the signal ingestion uses to materialise a ``placeholder`` row (B17).
    """

    caller_address: int
    callee_address: int
    callee_module: str | None = None


class GhidraExportBinary(ApiModel):
    """Binary metadata from the export (maps to ``RawBinary``).

    ``version`` is free text (AS11); the exporter defaults it to ``""``.
    ``sha256``/``function_count``/``edge_count`` are informational only — the
    server recomputes counts from what it actually ingested.
    """

    name: str
    version: str = ""
    source_path: str | None = None
    sha256: str | None = None
    function_count: int | None = None
    edge_count: int | None = None


class GhidraExportDocument(ApiModel):
    """A full Ghidra export file (the request body of ``POST /binaries/import``)."""

    schema_version: int
    binary: GhidraExportBinary
    functions: list[GhidraExportFunction] = Field(default_factory=list)
    edges: list[GhidraExportEdge] = Field(default_factory=list)


class ImportResultDto(ApiModel):
    """Outcome of an import, returned synchronously (I12).

    No SSE ``binary`` event is emitted (that transport is unbuilt in M0); the
    client refetches ``GET /binaries`` on success instead.
    """

    binary_id: int
    name: str
    version: str
    functions_inserted: int
    functions_updated: int
    edges_inserted: int
    placeholders_created: int
    failures: list[str] = Field(default_factory=list)
