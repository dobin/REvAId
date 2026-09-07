"""Graph-export import DTOs (I12 — file-based ingestion).

The wire shape accepts the legacy JSON produced by
``tools/ghidra/GraphRevExport.java`` (schemas v1 and v2) and Kuna's
``decompile-graph`` schema v4. These DTOs are the *only* validation boundary
for an uploaded export — everything past :class:`GhidraExportDocument` is
trusted, already-typed data fed into the ingestion pipeline via
:class:`graphrev.adapters.ghidra.file.FileGhidraAdapter`.

Field names are ``camelCase`` on the wire (matching the exporter and the rest
of the API, TAD §4) and ``snake_case`` in Python via :class:`ApiModel`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from graphrev.db.enums import EdgeKind, FunctionKind
from graphrev.schemas.common import ApiModel

#: Schema v2 adds per-caller ``calleeOrder``; Kuna schema v4 adds ``data``
#: function rows and ``call``/``jump``/``data`` edge kinds. v1 remains
#: accepted so existing exports can still be imported as unordered.
SUPPORTED_EXPORT_SCHEMA_VERSIONS = frozenset({1, 2, 4})

#: Kuna's ``data`` rows have no executable body. GraphRev stores them as the
#: existing ``external`` kind while retaining all supported executable kinds.
ExportFunctionKind = FunctionKind | Literal["data"]


class GhidraExportParam(ApiModel):
    """One decompiled parameter (maps to ``RawParam``)."""

    ordinal: int
    name: str
    type: str


class GhidraExportFunction(ApiModel):
    """One exported function (maps to ``RawFunction``).

    ``placeholder`` is never supplied by an adapter — it is materialised by
    ingestion from unresolved cross-module edges (B17). Kuna schema v4 also
    reports non-executable address rows as ``data``.
    """

    address: int
    name: str
    parameters: list[GhidraExportParam] = Field(default_factory=list)
    signature: str | None = None
    assembly: str | None = None
    code_c: str | None = None
    kind: ExportFunctionKind = "normal"
    has_indirect_calls: bool = False
    is_entry_point: bool = False


class GhidraExportEdge(ApiModel):
    """One caller -> callee edge (maps to ``RawEdge``).

    ``callee_module`` is set when the callee lives outside this binary; that
    is the signal ingestion uses to materialise a ``placeholder`` row (B17).
    """

    caller_address: int
    callee_address: int
    kind: EdgeKind = "call"
    callee_module: str | None = None
    #: Schema-v2 static first-call-site ordinal. ``None`` represents a legacy
    #: schema-v1 export, which has no trustworthy imported order.
    callee_order: int | None = Field(default=None, ge=0)


class GhidraExportBinary(ApiModel):
    """Binary metadata from the export (maps to ``RawBinary``).

    ``version`` is free text (AS11); the exporter defaults it to ``""``.
    ``sha256`` is the preferred content identity. It remains optional for
    legacy exports; ``function_count``/``edge_count`` are informational only.
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

    @field_validator("sha256")
    @classmethod
    def _normalise_sha256(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalised = value.lower()
        if len(normalised) != 64 or any(c not in "0123456789abcdef" for c in normalised):
            raise ValueError("sha256 must be exactly 64 hexadecimal characters")
        return normalised


class GhidraExportDocument(ApiModel):
    """A full Ghidra export file (the request body of ``POST /binaries/import``)."""

    schema_version: int
    binary: GhidraExportBinary
    functions: list[GhidraExportFunction] = Field(default_factory=list)
    edges: list[GhidraExportEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_callee_order(self) -> GhidraExportDocument:
        """Enforce v2/v4's distinct, contiguous per-caller order contract."""
        if self.schema_version not in {2, 4}:
            return self

        orders_by_caller: dict[int, list[int]] = {}
        seen_pairs: set[tuple[int, int]] = set()
        for edge in self.edges:
            if edge.callee_order is None:
                raise ValueError(
                    f"schemaVersion {self.schema_version} requires calleeOrder on every edge"
                )
            pair = (edge.caller_address, edge.callee_address)
            if pair in seen_pairs:
                raise ValueError(
                    f"schemaVersion {self.schema_version} must not contain duplicate "
                    "callerAddress/calleeAddress pairs"
                )
            seen_pairs.add(pair)
            orders_by_caller.setdefault(edge.caller_address, []).append(edge.callee_order)

        for caller_address, orders in orders_by_caller.items():
            if sorted(orders) != list(range(len(orders))):
                raise ValueError(
                    f"schemaVersion {self.schema_version} calleeOrder values for "
                    f"callerAddress {caller_address} "
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
    DECOMPILING = "decompiling"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ImportJobAcceptedDto(ApiModel):
    """Returned as soon as a raw export has been staged safely."""

    job_id: str
    phase: ImportJobPhase
    bytes_received: int
    source_kind: str


class ImportJobStatusDto(ApiModel):
    """Process-local import-job state.

    Jobs intentionally do not survive an API process restart in this first
    scalable-import iteration. `failure_samples` is bounded by configuration.
    """

    job_id: str
    phase: ImportJobPhase
    bytes_received: int
    source_kind: str
    result: ImportResultDto | None = None
    error_message: str | None = None
    error_code: str | None = None
    error_details: dict[str, Any] | None = None
    failure_samples: list[str] = Field(default_factory=list)
