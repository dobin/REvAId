"""``GhidraAdapter`` Protocol + raw DTOs (TAD §6.3, A2, A5).

This is the contract a real Ghidra integration must satisfy so M1 (`I12`) can
be implemented with zero changes to ``ingestion/``, ``services/``, or the API
surface. M0 ships only :class:`~graphrev.adapters.ghidra.mock.MockGhidraAdapter`
behind this same Protocol.

Only this package's own ``__init__.py`` may import the concrete
``mock``/``rest`` modules (enforced by the ``import-linter`` "Only
adapters/*/base may be imported outside their own package" contract in
``pyproject.toml``) — every other caller (``ingestion``, ``cli``, ...) depends
on this module only.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol, TypedDict

from graphrev.db.enums import FunctionKind


class RawParam(TypedDict):
    """One decompiled parameter, as reported by Ghidra."""

    ordinal: int
    name: str
    type: str


@dataclass(frozen=True, slots=True)
class RawBinary:
    """One binary as reported by :meth:`GhidraAdapter.list_binaries`."""

    name: str
    version: str
    source_path: str | None = None
    analysis_image_base: int | None = None


@dataclass(frozen=True, slots=True)
class RawBinaryRef:
    """The subset of :class:`RawBinary` needed to address a binary for
    :meth:`GhidraAdapter.iter_functions`/``iter_edges``/``get_function``.

    A thin alias rather than a second full dataclass — TAD §6.3 names
    ``RawBinaryRef`` distinctly from ``RawBinary`` but a binary is uniquely
    identified by ``(name, version)`` (``ux_binaries_name_version``), so no
    additional fields are needed to look it up.
    """

    name: str
    version: str


@dataclass(frozen=True, slots=True)
class RawFunction:
    """One function as reported by Ghidra, pre-ingestion.

    ``assembly``/``code_c`` are ``None`` for import/thunk/external/placeholder
    functions (B17) — there is nothing to decompile.

    ``has_indirect_calls`` feeds I4's ``mayBeIncomplete`` neighbour-table
    footer hint; persisted to ``functions.has_indirect_calls`` (I4, migration
    ``0003``).
    """

    address: int
    name: str
    parameters: tuple[RawParam, ...]
    signature: str | None
    assembly: str | None
    code_c: str | None
    kind: FunctionKind
    has_indirect_calls: bool = False
    #: I3/E1b: true for a function the adapter considers a natural entry
    #: point (e.g. a real PE entrypoint, or `main`-equivalent). Ingestion
    #: seeds `functions.is_entry_point` from this only on first INSERT — it
    #: is analyst-owned thereafter (never overwritten on re-ingest).
    is_entry_point: bool = False


@dataclass(frozen=True, slots=True)
class RawEdge:
    """One caller -> callee edge, addressed rather than ID-based.

    ``callee_module`` is set when the callee is known to live outside the
    binary currently being ingested (e.g. a call from ``acme.exe`` into
    ``libparse.dll``) — this is exactly the signal ``ingestion/pipeline.py``
    uses to materialise a ``kind='placeholder'`` function row (B17) instead of
    violating the ``edges`` foreign keys.
    """

    caller_address: int
    callee_address: int
    callee_module: str | None = None
    #: Static first-call-site ordinal from schema-v2 exports; ``None`` when an
    #: adapter or legacy source cannot report a trustworthy order.
    callee_order: int | None = None


class GhidraAdapter(Protocol):
    """Ghidra access, abstracted behind an interface (A2).

    Implementations: :class:`~graphrev.adapters.ghidra.mock.MockGhidraAdapter`
    (M0) and a future ``RestGhidraAdapter``/MCP bridge (M1, `I12`) — selected
    at runtime via :func:`graphrev.adapters.ghidra.create_adapter`, never
    imported directly outside this package.
    """

    def list_binaries(self) -> Sequence[RawBinary]:
        """All binaries this adapter can ingest."""
        ...

    def iter_functions(self, binary: RawBinaryRef) -> Iterator[RawFunction]:
        """Every function in ``binary``, in adapter-defined order."""
        ...

    def iter_edges(self, binary: RawBinaryRef) -> Iterator[RawEdge]:
        """Every caller -> callee edge in ``binary``."""
        ...

    def get_function(self, binary: RawBinaryRef, address: int) -> RawFunction | None:
        """A single function by address (A6 incremental/on-demand ingestion)."""
        ...
