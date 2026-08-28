"""Ghidra JSON-export import DTOs (I12 — file-based ingestion).

The wire shape mirrors the JSON produced by ``tools/ghidra/GraphRevExport.java``
(schemas v1 and v2). These DTOs are the *only* validation boundary for an uploaded
export — everything past :class:`GhidraExportDocument` is trusted, already-typed
data fed into the ingestion pipeline via
:class:`graphrev.adapters.ghidra.file.FileGhidraAdapter`.

Field names are ``camelCase`` on the wire (matching the exporter and the rest
of the API, TAD §4) and ``snake_case`` in Python via :class:`ApiModel`.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from graphrev.db.enums import FunctionKind
from graphrev.schemas.common import ApiModel

#: Versions accepted by this build. Schema v2 adds per-caller ``calleeOrder``;
#: v1 remains accepted so existing exports can still be imported as unordered.
SUPPORTED_EXPORT_SCHEMA_VERSIONS = frozenset({1, 2})


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
    #: Schema-v2 static first-call-site ordinal. ``None`` represents a legacy
    #: schema-v1 export, which has no trustworthy imported order.
    callee_order: int | None = Field(default=None, ge=0)


class GhidraExportBinary(ApiModel):
    """Binary metadata from the export (maps to ``RawBinary``).

    ``version`` is free text (AS11); the exporter defaults it to ``""``.
    ``sha256``/``function_count``/``edge_count`` are informational only — the
    server recomputes counts from what it actually ingested.
    """

    name: str
    version: str = ""
    source_path: str | None = None
    #: Static Ghidra image base captured by the exporter. Nullable for legacy
    #: schema-v1 files, which cannot be rebased from runtime process VAs.
    analysis_image_base: int | None = None
    sha256: str | None = None
    function_count: int | None = None
    edge_count: int | None = None


class GhidraExportDocument(ApiModel):
    """A full Ghidra export file (the request body of ``POST /binaries/import``)."""

    schema_version: int
    binary: GhidraExportBinary
    functions: list[GhidraExportFunction] = Field(default_factory=list)
    edges: list[GhidraExportEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_callee_order(self) -> GhidraExportDocument:
        """Enforce schema-v2's distinct, contiguous per-caller order contract."""
        if self.schema_version != 2:
            return self

        orders_by_caller: dict[int, list[int]] = {}
        seen_pairs: set[tuple[int, int]] = set()
        for edge in self.edges:
            if edge.callee_order is None:
                raise ValueError("schemaVersion 2 requires calleeOrder on every edge")
            pair = (edge.caller_address, edge.callee_address)
            if pair in seen_pairs:
                raise ValueError(
                    "schemaVersion 2 must not contain duplicate callerAddress/calleeAddress pairs"
                )
            seen_pairs.add(pair)
            orders_by_caller.setdefault(edge.caller_address, []).append(edge.callee_order)

        for caller_address, orders in orders_by_caller.items():
            if sorted(orders) != list(range(len(orders))):
                raise ValueError(
                    f"schemaVersion 2 calleeOrder values for callerAddress {caller_address} "
                    "must be contiguous from 0"
                )
        return self


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


class ImportJobPhase(StrEnum):
    """Observable phases for a staged Ghidra import."""

    UPLOADING = "uploading"
    QUEUED = "queued"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImportJobAcceptedDto(ApiModel):
    """Returned as soon as a raw export has been staged safely."""

    job_id: str
    phase: ImportJobPhase
    bytes_received: int


class ImportJobStatusDto(ApiModel):
    """Process-local import-job state.

    Jobs intentionally do not survive an API process restart in this first
    scalable-import iteration. `failure_samples` is bounded by configuration.
    """

    job_id: str
    phase: ImportJobPhase
    bytes_received: int
    result: ImportResultDto | None = None
    error_message: str | None = None
    failure_samples: list[str] = Field(default_factory=list)
