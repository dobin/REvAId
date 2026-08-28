"""File-based :class:`GhidraAdapter` over a parsed JSON export (I12).

Consumes the schema produced by ``tools/ghidra/GraphRevExport.java`` (validated
into a :class:`~graphrev.schemas.ingest.GhidraExportDocument` before it reaches
here) and presents it through the same Protocol the mock adapter satisfies, so
``ingestion/pipeline.py`` ingests a real export with zero pipeline changes
(AS14).

Unlike the mock, this adapter carries exactly one binary — the one in the
uploaded document. ``list_binaries`` therefore returns a single-element
sequence, and the ``iter_*``/``get_function`` methods ignore the ``name`` in
the passed :class:`RawBinaryRef` beyond an assertion, since there is only ever
one binary to serve.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from graphrev.adapters.ghidra.base import (
    GhidraAdapter,
    RawBinary,
    RawBinaryRef,
    RawEdge,
    RawFunction,
    RawParam,
)
from graphrev.schemas.ingest import (
    GhidraExportDocument,
    GhidraExportEdge,
    GhidraExportFunction,
)


def _to_raw_function(fn: GhidraExportFunction) -> RawFunction:
    parameters: tuple[RawParam, ...] = tuple(
        RawParam(ordinal=p.ordinal, name=p.name, type=p.type) for p in fn.parameters
    )
    return RawFunction(
        address=fn.address,
        name=fn.name,
        parameters=parameters,
        signature=fn.signature,
        assembly=fn.assembly,
        code_c=fn.code_c,
        kind=fn.kind,
        has_indirect_calls=fn.has_indirect_calls,
        is_entry_point=fn.is_entry_point,
    )


def _to_raw_edge(edge: GhidraExportEdge) -> RawEdge:
    return RawEdge(
        caller_address=edge.caller_address,
        callee_address=edge.callee_address,
        callee_module=edge.callee_module,
        callee_order=edge.callee_order,
    )


class FileGhidraAdapter:
    """A :class:`GhidraAdapter` backed by one parsed export document."""

    def __init__(self, document: GhidraExportDocument) -> None:
        self._binary = RawBinary(
            name=document.binary.name,
            version=document.binary.version,
            source_path=document.binary.source_path,
            analysis_image_base=document.binary.analysis_image_base,
        )
        self._functions: list[RawFunction] = [_to_raw_function(fn) for fn in document.functions]
        self._edges: list[RawEdge] = [_to_raw_edge(edge) for edge in document.edges]

    def list_binaries(self) -> Sequence[RawBinary]:
        return (self._binary,)

    def iter_functions(self, binary: RawBinaryRef) -> Iterator[RawFunction]:
        assert binary.name == self._binary.name
        yield from self._functions

    def iter_edges(self, binary: RawBinaryRef) -> Iterator[RawEdge]:
        assert binary.name == self._binary.name
        yield from self._edges

    def get_function(self, binary: RawBinaryRef, address: int) -> RawFunction | None:
        assert binary.name == self._binary.name
        for fn in self._functions:
            if fn.address == address:
                return fn
        return None


def _typecheck_conforms(adapter: FileGhidraAdapter) -> GhidraAdapter:
    """Static assertion that :class:`FileGhidraAdapter` satisfies the Protocol."""
    return adapter
