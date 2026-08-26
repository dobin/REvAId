"""Deterministic synthetic Ghidra data for UI development (A2, A7, A7a, A8).

:class:`MockGhidraAdapter` is a *functional* requirement, not test scaffolding
(TAD §6.3) — the whole M0 exit criteria depends on its output shape. Given the
same ``seed`` it must produce byte-identical output.

Topology built (TAD §6.3 mock spec):
  * Two binaries: ``acme.exe`` and ``libparse.dll`` (A7).
  * A shallow entry region (``main`` -> 12 callees).
  * Four 4-deep parser chains.
  * One function with 34 callees and one with 300+ callees (a "dispatcher"),
    both drawing callees from a shared leaf/utility pool so the population
    needed to host a genuinely large fan-out/fan-in graph is not duplicated.
  * At least three "memcpy-class" fan-in hubs with `fan_in > 50`, one with
    ~291 callers (A7a) — deliberately chosen to exercise `D7` caller
    suppression (`CALLER_SUPPRESS_THRESHOLD` default 32) at exactly the
    wireframed number.
  * A shared helper (``check_config``) called by ``main`` directly *and* by
    two ``entry_child_*`` functions — exercising the "multiple callers at
    different depths" pattern (fan_in = 3, callers at depth 0 and depth 1).
  * A self-recursive function and a mutual-recursion pair.
  * A handful of orphans (no callers, no callees).
  * One function of each non-placeholder `kind` (`normal`, `import`,
    `thunk`, `external`) (A8); `placeholder` rows are never emitted directly
    — they arise in `ingestion/pipeline.py` from the unresolved cross-binary
    edges built here (B17).

Note on population size: TAD §6.3 describes ``acme.exe`` as "~180 functions".
That figure and the mandatory "one function with 300+ callees" are only
reconcilable if a single binary's function population is large enough to
*host* 300+ distinct callees plus a ~291-caller hub — which, in a directed
call graph without external stand-ins, requires several hundred functions to
exist somewhere in that same binary. This module therefore produces a larger
population than the approximate "~180" figure in order to satisfy the exact
counts the TAD's own exit tests assert (`fan_in > 50`, `>= 291` callers,
`>= 300` callees) without inventing functions that exist for no structural
reason.
"""

from __future__ import annotations

import random
from collections.abc import Iterator, Sequence

from graphrev.adapters.ghidra.base import (
    GhidraAdapter,
    RawBinary,
    RawBinaryRef,
    RawEdge,
    RawFunction,
    RawParam,
)
from graphrev.adapters.mock_summaries import MOCK_LLM_NAMES, MOCK_SUMMARIES

#: A7: at least two distinct synthetic binaries.
ACME_EXE = RawBinary(name="acme.exe", version="1.0")
LIBPARSE_DLL = RawBinary(name="libparse.dll", version="1.0")

#: A7a: the wireframed hub size (D7's `CALLER_SUPPRESS_THRESHOLD` default is
#: 32; TAD's own exit test for I4 names 291 explicitly).
_BIG_HUB_CALLER_COUNT = 291
_MEDIUM_HUB_CALLER_COUNT = 120
_SMALL_HUB_CALLER_COUNT = 60
_LEAF_POOL_SIZE = 300
_HUB34_CALLEE_COUNT = 34


class _AddressAllocator:
    """Monotonically increasing fake virtual addresses, one per function."""

    def __init__(self, start: int, step: int = 0x20) -> None:
        self._next = start
        self._step = step

    def take(self) -> int:
        addr = self._next
        self._next += self._step
        return addr


def _make_function(
    name: str,
    addr: int,
    *,
    kind: str = "normal",
    has_code: bool = True,
    has_indirect_calls: bool = False,
    is_entry_point: bool = False,
) -> RawFunction:
    """Build one `RawFunction`. `has_code=False` models import/thunk/external
    (B17: `assembly`/`code_c` are `NULL` for these `kind`s)."""
    params: tuple[RawParam, ...] = (
        (RawParam(ordinal=0, name="arg0", type="int"),) if kind == "normal" else ()
    )
    return RawFunction(
        address=addr,
        name=name,
        parameters=params,
        signature=f"int {name}(int)" if kind == "normal" else None,
        assembly=f"; disassembly of {name}" if has_code else None,
        code_c=f"int {name}(int arg0) {{ return arg0; }}" if has_code else None,
        kind=kind,  # type: ignore[arg-type]
        has_indirect_calls=has_indirect_calls,
        is_entry_point=is_entry_point,
    )


def _build_acme_exe(rng: random.Random) -> tuple[list[RawFunction], list[RawEdge]]:
    alloc = _AddressAllocator(start=0x00401000)
    functions: list[RawFunction] = []
    edges: list[RawEdge] = []

    # -- 1. entry region: main -> 12 callees ---------------------------------
    main_addr = alloc.take()
    functions.append(_make_function("main", main_addr, is_entry_point=True))
    entry_children: list[RawFunction] = []
    for i in range(12):
        addr = alloc.take()
        fn = _make_function(f"entry_child_{i:02d}", addr)
        functions.append(fn)
        entry_children.append(fn)
        edges.append(RawEdge(caller_address=main_addr, callee_address=addr))

    # -- 1b. shared helper called by main directly AND by some entry children --
    # This exercises the "multiple callers at different depths" pattern:
    # main -> check_config, and also main -> entry_child_04 -> check_config.
    shared_helper_addr = alloc.take()
    functions.append(_make_function("check_config", shared_helper_addr))
    edges.append(RawEdge(caller_address=main_addr, callee_address=shared_helper_addr))
    # entry_child_04 and entry_child_07 also call it, giving fan_in = 3
    for child_idx in (4, 7):
        edges.append(
            RawEdge(
                caller_address=entry_children[child_idx].address,
                callee_address=shared_helper_addr,
            )
        )

    # -- 2. four 4-deep parser chains -----------------------------------------
    for c in range(4):
        prev_addr: int | None = None
        for d in range(4):
            addr = alloc.take()
            functions.append(_make_function(f"parse_chain{c}_{d}", addr))
            if prev_addr is None:
                caller_addr = entry_children[c % len(entry_children)].address
            else:
                caller_addr = prev_addr
            edges.append(RawEdge(caller_address=caller_addr, callee_address=addr))
            prev_addr = addr

    # -- 3. shared leaf/utility pool -------------------------------------------
    # Callee population for the 34-/300-callee functions and caller population
    # for the fan-in hubs below, so the graph is realistically dense rather
    # than requiring a separate function for every edge endpoint.
    leaf_pool: list[RawFunction] = []
    for i in range(_LEAF_POOL_SIZE):
        addr = alloc.take()
        fn = _make_function(f"util_fn_{i:03d}", addr)
        functions.append(fn)
        leaf_pool.append(fn)

    # -- 4. one function with 34 callees (D6/D34 table-scroll exercise) -------
    hub34_addr = alloc.take()
    functions.append(_make_function("dispatch_small", hub34_addr))
    for leaf in rng.sample(leaf_pool, _HUB34_CALLEE_COUNT):
        edges.append(RawEdge(caller_address=hub34_addr, callee_address=leaf.address))

    # -- 5. one function with 300+ callees (the "dispatcher") ------------------
    dispatcher_addr = alloc.take()
    functions.append(_make_function("dispatch_large", dispatcher_addr, has_indirect_calls=True))
    for leaf in leaf_pool:
        edges.append(RawEdge(caller_address=dispatcher_addr, callee_address=leaf.address))

    # -- 6. memcpy-class fan-in hubs: >=3 functions with fan_in > 50 -----------
    for hub_name, caller_count in (
        ("mem_copy_block", _BIG_HUB_CALLER_COUNT),
        ("mem_set_block", _MEDIUM_HUB_CALLER_COUNT),
        ("str_length", _SMALL_HUB_CALLER_COUNT),
    ):
        hub_addr = alloc.take()
        functions.append(_make_function(hub_name, hub_addr))
        for caller in rng.sample(leaf_pool, caller_count):
            edges.append(RawEdge(caller_address=caller.address, callee_address=hub_addr))

    # -- 7. self-recursion ------------------------------------------------------
    rec_addr = alloc.take()
    functions.append(_make_function("walk_tree_recursive", rec_addr))
    edges.append(RawEdge(caller_address=rec_addr, callee_address=rec_addr))

    # -- 8. mutual recursion pair -------------------------------------------------
    mutual_a_addr = alloc.take()
    functions.append(_make_function("eval_expr", mutual_a_addr))
    mutual_b_addr = alloc.take()
    functions.append(_make_function("eval_term", mutual_b_addr))
    edges.append(RawEdge(caller_address=mutual_a_addr, callee_address=mutual_b_addr))
    edges.append(RawEdge(caller_address=mutual_b_addr, callee_address=mutual_a_addr))

    # Wire the structural roots into the reachable graph from `main` so they
    # are not themselves orphans.
    for reachable_addr in (hub34_addr, dispatcher_addr, rec_addr, mutual_a_addr):
        edges.append(RawEdge(caller_address=main_addr, callee_address=reachable_addr))

    # -- 9. orphans: no callers, no callees --------------------------------------
    for i in range(5):
        addr = alloc.take()
        functions.append(_make_function(f"orphan_fn_{i}", addr))

    # -- 10. one of each non-placeholder kind (A8) -------------------------------
    import_addr = alloc.take()
    functions.append(
        _make_function("__imp_LoadLibraryA", import_addr, kind="import", has_code=False)
    )
    thunk_addr = alloc.take()
    functions.append(_make_function("j_LoadLibraryA", thunk_addr, kind="thunk", has_code=False))
    external_addr = alloc.take()
    functions.append(
        _make_function("KERNEL32.dll::CreateFileW", external_addr, kind="external", has_code=False)
    )

    # -- 11. cross-binary unresolved edges -> libparse.dll (B17 placeholders) --
    unresolved_targets = (0x10005000, 0x10005040, 0x10005080)
    for i, unresolved_addr in enumerate(unresolved_targets):
        edges.append(
            RawEdge(
                caller_address=entry_children[i].address,
                callee_address=unresolved_addr,
                callee_module="libparse.dll",
            )
        )

    return functions, edges


def _build_libparse_dll(rng: random.Random) -> tuple[list[RawFunction], list[RawEdge]]:
    del rng  # no randomised structure needed for this smaller binary
    alloc = _AddressAllocator(start=0x10001000)
    functions: list[RawFunction] = []
    edges: list[RawEdge] = []

    root_addr = alloc.take()
    functions.append(_make_function("parse_document", root_addr, is_entry_point=True))

    prev_addr = root_addr
    for name in ("parse_section", "parse_field", "parse_value", "parse_literal"):
        addr = alloc.take()
        functions.append(_make_function(name, addr))
        edges.append(RawEdge(caller_address=prev_addr, callee_address=addr))
        prev_addr = addr

    # Fill out to ~60 functions with flat helpers called directly by the root.
    target_total = 60
    kind_variety_count = 3
    remaining = target_total - len(functions) - kind_variety_count
    for i in range(remaining):
        addr = alloc.take()
        fn = _make_function(f"lp_helper_{i:03d}", addr)
        functions.append(fn)
        edges.append(RawEdge(caller_address=root_addr, callee_address=addr))

    import_addr = alloc.take()
    functions.append(_make_function("__imp_malloc", import_addr, kind="import", has_code=False))
    thunk_addr = alloc.take()
    functions.append(_make_function("j_malloc", thunk_addr, kind="thunk", has_code=False))
    external_addr = alloc.take()
    functions.append(
        _make_function("msvcrt.dll::memmove", external_addr, kind="external", has_code=False)
    )

    return functions, edges


class MockGhidraAdapter:
    """A2: the mock `GhidraAdapter` implementation.

    Given the same ``seed``, every method returns byte-identical output —
    asserted by `tests/unit/test_mock_ghidra_adapter.py`. Structure (topology,
    counts, kinds) is deterministic by construction; `seed` additionally
    drives which specific leaf-pool functions are wired into each fan-out/
    fan-in structure via `random.Random.sample`.
    """

    def __init__(self, seed: int = 1337) -> None:
        self._seed = seed
        rng = random.Random(seed)
        self._data: dict[str, tuple[list[RawFunction], list[RawEdge]]] = {
            ACME_EXE.name: _build_acme_exe(rng),
            LIBPARSE_DLL.name: _build_libparse_dll(rng),
        }

    def list_binaries(self) -> Sequence[RawBinary]:
        return (ACME_EXE, LIBPARSE_DLL)

    def iter_functions(self, binary: RawBinaryRef) -> Iterator[RawFunction]:
        functions, _ = self._data[binary.name]
        yield from functions

    def iter_edges(self, binary: RawBinaryRef) -> Iterator[RawEdge]:
        _, edges = self._data[binary.name]
        yield from edges

    def get_function(self, binary: RawBinaryRef, address: int) -> RawFunction | None:
        functions, _ = self._data[binary.name]
        for fn in functions:
            if fn.address == address:
                return fn
        return None


#: Structural self-check: `MockGhidraAdapter` satisfies `GhidraAdapter` at
#: type-check time (Protocol, so this is a static assertion, never instantiated).
def _typecheck_conforms(adapter: MockGhidraAdapter) -> GhidraAdapter:
    return adapter


# ---------------------------------------------------------------------------
# Fake LLM summaries for UI development
# ---------------------------------------------------------------------------
# The corpus itself now lives in `adapters/mock_summaries.py` (shared with
# `adapters/llm/mock.py::MockLlmAdapter` so both mocks agree on the same
# fake content) — see that module's docstring for why importing it here does
# not violate the "only adapters/*/base outside the package" import-linter
# contract.


async def seed_mock_summaries(session_factory: "async_sessionmaker") -> int:  # type: ignore[type-arg]
    """Inject fake LLM summaries into the DB for UI development.

    Only updates rows where *summary_status* is still ``'none'`` so a real
    summarisation run is not overwritten.  Returns the number of rows updated.
    """
    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: F401 (type hint only)

    from graphrev.db.models import Function

    updated = 0
    async with session_factory() as session:
        async with session.begin():
            for name, (short, long_) in MOCK_SUMMARIES.items():
                result = await session.execute(
                    select(Function.id).where(
                        Function.name_ghidra == name,
                        Function.summary_status == "none",
                    )
                )
                ids = [row[0] for row in result.all()]
                if not ids:
                    continue
                await session.execute(
                    update(Function)
                    .where(Function.id.in_(ids))
                    .values(
                        summary_short=short,
                        summary_long=long_,
                        name_llm=MOCK_LLM_NAMES.get(name),
                        summary_status="ready",
                        summary_model="mock-llm-v1",
                        summary_generated_at="2026-08-22T00:00:00Z",
                    )
                )
                updated += len(ids)
    return updated
