"""Ingestion pipeline: idempotency (A3), placeholder upgrade (B17), per-item
failure isolation (A4), fan-in/utility recompute (A7a), and F1b bookkeeping."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from graphrev.adapters.ghidra.base import (
    RawBinary,
    RawBinaryRef,
    RawEdge,
    RawFunction,
)
from graphrev.adapters.ghidra.mock import MockGhidraAdapter
from graphrev.core.config import Settings
from graphrev.db.models import Function, View
from graphrev.ingestion.pipeline import run_ingestion


class _FakeAdapter:
    """A tiny hand-rolled `GhidraAdapter` for behavioural tests that need
    exact control over what changes between two ingestion runs."""

    def __init__(
        self,
        functions: list[RawFunction],
        edges: list[RawEdge],
        *,
        raise_for_address: int | None = None,
    ) -> None:
        self._functions = functions
        self._edges = edges
        self._raise_for_address = raise_for_address

    def list_binaries(self) -> Sequence[RawBinary]:
        return (RawBinary(name="fake.exe", version="1.0"),)

    def iter_functions(self, binary: RawBinaryRef) -> Iterator[RawFunction]:
        for fn in self._functions:
            if fn.address == self._raise_for_address:
                # Raised lazily, mid-iteration — simulates a Ghidra decompile
                # failure surfaced while walking the function list, not a
                # bad upsert. The generator is closed by Python after this
                # raise, so nothing after it in `self._functions` is ever
                # produced; the pipeline must still finish the binary using
                # whatever was yielded before the failure.
                raise RuntimeError(f"boom at 0x{fn.address:x}")
            yield fn

    def iter_edges(self, binary: RawBinaryRef) -> Iterator[RawEdge]:
        yield from self._edges

    def get_function(self, binary: RawBinaryRef, address: int) -> RawFunction | None:
        for fn in self._functions:
            if fn.address == address:
                return fn
        return None


def _fn(address: int, name: str, kind: str = "normal") -> RawFunction:
    return RawFunction(
        address=address,
        name=name,
        parameters=(),
        signature=None,
        assembly=f"; {name}" if kind == "normal" else None,
        code_c=f"int {name}(void) {{ return 0; }}" if kind == "normal" else None,
        kind=kind,  # type: ignore[arg-type]
    )


class _MultiBinaryFakeAdapter:
    """A `GhidraAdapter` returning several tiny binaries, for pipeline
    behaviours that need the *multi-binary* shape (default-view-per-binary,
    cross-binary idempotency) but not the ~560-function scale of the real
    `MockGhidraAdapter`. Keeping these behavioural tests on a handful of rows
    keeps them fast; the full mock's realistic scale is still exercised by the
    `slow` CLI tests and the api-suite ingested template."""

    def __init__(self, binaries: dict[str, tuple[list[RawFunction], list[RawEdge]]]) -> None:
        self._binaries = binaries

    def list_binaries(self) -> Sequence[RawBinary]:
        return [RawBinary(name=name, version="1.0") for name in self._binaries]

    def iter_functions(self, binary: RawBinaryRef) -> Iterator[RawFunction]:
        yield from self._binaries[binary.name][0]

    def iter_edges(self, binary: RawBinaryRef) -> Iterator[RawEdge]:
        yield from self._binaries[binary.name][1]

    def get_function(self, binary: RawBinaryRef, address: int) -> RawFunction | None:
        for fn in self._binaries[binary.name][0]:
            if fn.address == address:
                return fn
        return None


def _two_binary_adapter() -> _MultiBinaryFakeAdapter:
    """Two small binaries with an intra-binary edge each — enough to prove
    multi-binary + edge idempotency without the mock's scale."""
    return _MultiBinaryFakeAdapter(
        {
            "acme.exe": (
                [_fn(0x1000, "main"), _fn(0x1010, "helper")],
                [RawEdge(caller_address=0x1000, callee_address=0x1010)],
            ),
            "libparse.dll": (
                [_fn(0x2000, "parse"), _fn(0x2010, "lex")],
                [RawEdge(caller_address=0x2000, callee_address=0x2010)],
            ),
        }
    )


@pytest.mark.asyncio
async def test_ingestion_is_idempotent_across_two_runs(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    """A3: a second run of the same input inserts nothing new and changes no
    row/edge counts. Behaviour is topology-independent, so a tiny two-binary
    fake proves it identically to the full mock — but ~100x faster."""
    adapter = _two_binary_adapter()

    reports1 = await run_ingestion(session_factory, adapter, settings)
    assert all(not r.binary_failed for r in reports1)

    async with session_factory() as session:
        function_count_1 = (
            await session.execute(text("SELECT COUNT(*) FROM functions"))
        ).scalar_one()
        edge_count_1 = (await session.execute(text("SELECT COUNT(*) FROM edges"))).scalar_one()

    reports2 = await run_ingestion(session_factory, adapter, settings)
    assert all(not r.binary_failed for r in reports2)

    async with session_factory() as session:
        function_count_2 = (
            await session.execute(text("SELECT COUNT(*) FROM functions"))
        ).scalar_one()
        edge_count_2 = (await session.execute(text("SELECT COUNT(*) FROM edges"))).scalar_one()

    assert function_count_1 == function_count_2
    assert edge_count_1 == edge_count_2
    # Second run should be all updates, no new inserts.
    assert sum(r.functions_inserted for r in reports2) == 0
    assert sum(r.functions_updated for r in reports2) > 0


@pytest.mark.asyncio
async def test_ingestion_creates_default_view_per_binary(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    """B9: every ingested binary gets exactly one default view. Uses a tiny
    two-binary fake — the assertion is per-binary, not per-function-count."""
    adapter = _two_binary_adapter()
    await run_ingestion(session_factory, adapter, settings)

    async with session_factory() as session:
        for name in ("acme.exe", "libparse.dll"):
            binary_id = (
                await session.execute(text("SELECT id FROM binaries WHERE name = :n"), {"n": name})
            ).scalar_one()
            views = (
                (await session.execute(select(View).where(View.binary_id == binary_id)))
                .scalars()
                .all()
            )
            assert len(views) == 1


@pytest.mark.asyncio
async def test_reingest_preserves_analyst_and_llm_fields_end_to_end(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    first_pass = _FakeAdapter(
        functions=[_fn(0x1000, "FUN_00001000")],
        edges=[],
    )
    await run_ingestion(session_factory, first_pass, settings)

    async with session_factory() as session:
        fn = (
            await session.execute(select(Function).where(Function.address == 0x1000))
        ).scalar_one()
        fn.summary_short = "Parses the on-disk configuration."
        fn.summary_status = "ready"
        fn.name_analyst = "parse_config"
        fn.notes = "Confirmed v2 format only."
        fn.utility_override = "never"
        function_id = fn.id
        await session.commit()

    second_pass = _FakeAdapter(
        functions=[_fn(0x1000, "parse_config_v2")],
        edges=[],
    )
    await run_ingestion(session_factory, second_pass, settings)

    async with session_factory() as session:
        refreshed = await session.get(Function, function_id)
        assert refreshed is not None
        assert refreshed.name_ghidra == "parse_config_v2"
        assert refreshed.summary_short == "Parses the on-disk configuration."
        assert refreshed.summary_status == "ready"
        assert refreshed.name_analyst == "parse_config"
        assert refreshed.notes == "Confirmed v2 format only."
        assert refreshed.utility_override == "never"


@pytest.mark.asyncio
async def test_unresolved_edge_creates_placeholder_then_upgrades_in_place(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    caller = _fn(0x1000, "caller_fn")
    first_pass = _FakeAdapter(
        functions=[caller],
        edges=[
            RawEdge(caller_address=0x1000, callee_address=0x50000000, callee_module="libparse.dll")
        ],
    )
    await run_ingestion(session_factory, first_pass, settings)

    async with session_factory() as session:
        placeholder = (
            await session.execute(select(Function).where(Function.address == 0x50000000))
        ).scalar_one()
        assert placeholder.kind == "placeholder"
        assert placeholder.name_ghidra == "libparse.dll!FUN_50000000"
        assert placeholder.placeholder_module == "libparse.dll"
        placeholder_id = placeholder.id

    # A later run resolves that same address as a real function in the same
    # binary (e.g. a fuller analysis pass) — the row upgrades in place.
    second_pass = _FakeAdapter(
        functions=[caller, _fn(0x50000000, "parse_section")],
        edges=[RawEdge(caller_address=0x1000, callee_address=0x50000000)],
    )
    await run_ingestion(session_factory, second_pass, settings)

    async with session_factory() as session:
        upgraded = await session.get(Function, placeholder_id)
        assert upgraded is not None
        assert upgraded.kind == "normal"
        assert upgraded.name_ghidra == "parse_section"
        assert upgraded.placeholder_module is None


@pytest.mark.asyncio
async def test_per_function_failure_does_not_abort_the_run(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    adapter = _FakeAdapter(
        functions=[_fn(0x1000, "good_fn_1"), _fn(0x2000, "bad_fn"), _fn(0x3000, "good_fn_2")],
        edges=[],
        raise_for_address=0x2000,
    )
    reports = await run_ingestion(session_factory, adapter, settings)

    assert len(reports) == 1
    report = reports[0]
    # The generator raises and is closed by Python at 0x2000, so anything
    # after it (`good_fn_2`) is never produced by this particular fake — the
    # pipeline still must not crash, must record the failure (A4), and must
    # have persisted everything yielded before the failure (`good_fn_1`).
    assert report.binary_failed is False
    assert report.failure_count >= 1
    assert report.functions_inserted == 1

    async with session_factory() as session:
        good = (
            await session.execute(select(Function).where(Function.address == 0x1000))
        ).scalar_one_or_none()
        assert good is not None
        assert good.name_ghidra == "good_fn_1"


@pytest.mark.asyncio
async def test_fan_in_and_is_utility_computed_after_ingestion(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    hub = _fn(0x1000, "hub_fn")
    caller_count = settings.utility_fanin_threshold + 5
    callers = [_fn(0x2000 + i * 0x10, f"caller_{i}") for i in range(caller_count)]
    edges = [RawEdge(caller_address=c.address, callee_address=hub.address) for c in callers]
    adapter = _FakeAdapter(functions=[hub, *callers], edges=edges)

    await run_ingestion(session_factory, adapter, settings)

    async with session_factory() as session:
        hub_row = (
            await session.execute(select(Function).where(Function.address == 0x1000))
        ).scalar_one()
        assert hub_row.fan_in == len(callers)
        assert hub_row.is_utility is True


@pytest.mark.asyncio
async def test_ingestion_writes_utility_threshold_bookkeeping(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    adapter = _FakeAdapter(functions=[_fn(0x1000, "a")], edges=[])
    await run_ingestion(session_factory, adapter, settings)

    async with session_factory() as session:
        value = (
            await session.execute(
                text("SELECT value FROM app_meta WHERE key = 'utility_fanin_threshold'")
            )
        ).scalar_one()
        assert value == str(settings.utility_fanin_threshold)


@pytest.mark.asyncio
async def test_binary_filter_only_ingests_matching_binary(
    session_factory: async_sessionmaker[AsyncSession], settings: Settings
) -> None:
    adapter = MockGhidraAdapter(seed=1337)
    reports = await run_ingestion(session_factory, adapter, settings, binary_filter="libparse.dll")

    assert len(reports) == 1
    assert reports[0].binary_name == "libparse.dll"

    async with session_factory() as session:
        acme_exists = (
            await session.execute(text("SELECT COUNT(*) FROM binaries WHERE name = 'acme.exe'"))
        ).scalar_one()
        assert acme_exists == 0
