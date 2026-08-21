"""A2/A7/A7a/A8: `MockGhidraAdapter` determinism and topology spec."""

from __future__ import annotations

from collections import Counter

import pytest

from graphrev.adapters.ghidra import create_adapter
from graphrev.adapters.ghidra.base import RawBinaryRef, RawEdge, RawFunction
from graphrev.adapters.ghidra.mock import MockGhidraAdapter

SEED = 1337


def _load(name: str) -> tuple[list[RawFunction], list[RawEdge]]:
    adapter = MockGhidraAdapter(seed=SEED)
    ref = RawBinaryRef(name=name, version="1.0")
    functions = list(adapter.iter_functions(ref))
    edges = list(adapter.iter_edges(ref))
    return functions, edges


def test_list_binaries_returns_at_least_two_distinct_binaries() -> None:
    adapter = MockGhidraAdapter(seed=SEED)
    binaries = adapter.list_binaries()
    assert len(binaries) >= 2
    names = {b.name for b in binaries}
    assert "acme.exe" in names
    assert "libparse.dll" in names


def test_same_seed_produces_identical_output() -> None:
    a1 = MockGhidraAdapter(seed=SEED)
    a2 = MockGhidraAdapter(seed=SEED)
    ref = RawBinaryRef(name="acme.exe", version="1.0")
    assert list(a1.iter_functions(ref)) == list(a2.iter_functions(ref))
    assert list(a1.iter_edges(ref)) == list(a2.iter_edges(ref))


def test_different_seeds_may_wire_leaf_pool_differently() -> None:
    ref = RawBinaryRef(name="acme.exe", version="1.0")
    a1 = MockGhidraAdapter(seed=1)
    a2 = MockGhidraAdapter(seed=2)
    edges1 = list(a1.iter_edges(ref))
    edges2 = list(a2.iter_edges(ref))
    # Structure (counts) is deterministic regardless of seed; exact wiring of
    # the sampled leaf-pool edges may differ.
    assert len(edges1) == len(edges2)


def test_acme_exe_has_hub_with_at_least_291_callers() -> None:
    functions, edges = _load("acme.exe")
    fn_by_addr = {f.address: f for f in functions}
    callee_counter: Counter[int] = Counter()
    for e in edges:
        callee_counter[e.callee_address] += 1
    max_fan_in = max(callee_counter.values())
    assert max_fan_in >= 291
    hub_addr = max(callee_counter, key=lambda addr: callee_counter[addr])
    assert hub_addr in fn_by_addr


def test_acme_exe_has_at_least_three_functions_with_fan_in_over_50() -> None:
    _, edges = _load("acme.exe")
    callee_counter: Counter[int] = Counter(e.callee_address for e in edges)
    hubs_over_50 = [addr for addr, count in callee_counter.items() if count > 50]
    assert len(hubs_over_50) >= 3


def test_acme_exe_has_dispatcher_with_300_plus_callees() -> None:
    _, edges = _load("acme.exe")
    caller_counter: Counter[int] = Counter(e.caller_address for e in edges)
    assert max(caller_counter.values()) >= 300


def test_acme_exe_has_self_recursive_function() -> None:
    _, edges = _load("acme.exe")
    assert any(e.caller_address == e.callee_address for e in edges)


def test_acme_exe_has_mutual_recursion_pair() -> None:
    _, edges = _load("acme.exe")
    pairs = {(e.caller_address, e.callee_address) for e in edges}
    mutual = [(a, b) for (a, b) in pairs if a != b and (b, a) in pairs]
    assert len(mutual) >= 1


def test_acme_exe_has_orphans() -> None:
    functions, edges = _load("acme.exe")
    connected: set[int] = set()
    for e in edges:
        connected.add(e.caller_address)
        connected.add(e.callee_address)
    orphans = [f for f in functions if f.address not in connected]
    assert len(orphans) >= 1


def test_acme_exe_has_all_non_placeholder_kinds() -> None:
    functions, _ = _load("acme.exe")
    kinds = {f.kind for f in functions}
    assert {"normal", "import", "thunk", "external"} <= kinds
    assert "placeholder" not in kinds


def test_acme_exe_has_unresolved_cross_binary_edges() -> None:
    functions, edges = _load("acme.exe")
    known_addrs = {f.address for f in functions}
    unresolved = [
        e
        for e in edges
        if e.callee_module == "libparse.dll" and e.callee_address not in known_addrs
    ]
    assert len(unresolved) >= 1


def test_import_and_thunk_functions_have_no_code() -> None:
    functions, _ = _load("acme.exe")
    for fn in functions:
        if fn.kind in ("import", "thunk", "external"):
            assert fn.assembly is None
            assert fn.code_c is None


def test_libparse_dll_has_around_60_functions() -> None:
    functions, _ = _load("libparse.dll")
    assert 55 <= len(functions) <= 65


def test_acme_exe_flags_exactly_main_as_entry_point() -> None:
    functions, _ = _load("acme.exe")
    entry_points = [f.name for f in functions if f.is_entry_point]
    assert entry_points == ["main"]


def test_libparse_dll_flags_exactly_parse_document_as_entry_point() -> None:
    functions, _ = _load("libparse.dll")
    entry_points = [f.name for f in functions if f.is_entry_point]
    assert entry_points == ["parse_document"]


def test_create_adapter_mock_returns_mock_ghidra_adapter() -> None:
    adapter = create_adapter("mock", seed=SEED)
    assert isinstance(adapter, MockGhidraAdapter)


def test_create_adapter_rest_raises_not_implemented() -> None:
    from graphrev.adapters.ghidra import GhidraAdapterNotImplementedError

    with pytest.raises(GhidraAdapterNotImplementedError):
        create_adapter("rest", seed=SEED)
