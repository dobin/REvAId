"""`GET /functions/{id}/neighbours` (I4, E2, E2a, E2b, E2c)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.db.models import Function, View


async def _get_binary_id(client: AsyncClient, name: str) -> int:
    binaries = (await client.get("/api/v1/binaries")).json()
    return int(next(b["id"] for b in binaries if b["name"] == name))


async def _get_function_id_by_name(client: AsyncClient, binary_id: int, name: str) -> int:
    search = (
        await client.get(f"/api/v1/binaries/{binary_id}/functions", params={"q": name})
    ).json()
    return int(next(r["id"] for r in search["rows"] if r["displayName"] == name))


async def _get_view_id(session: AsyncSession, binary_id: int) -> int:
    result = await session.execute(select(View.id).where(View.binary_id == binary_id).limit(1))
    return result.scalar_one()


@pytest.mark.asyncio
async def test_neighbours_requires_view_id(client: AsyncClient, ingested: None) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    function_id = await _get_function_id_by_name(client, binary_id, "main")

    response = await client.get(f"/api/v1/functions/{function_id}/neighbours")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_main_callees_primary_page_shape(
    client: AsyncClient, session: AsyncSession, ingested: None
) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    function_id = await _get_function_id_by_name(client, binary_id, "main")
    view_id = await _get_view_id(session, binary_id)

    response = await client.get(
        f"/api/v1/functions/{function_id}/neighbours",
        params={"viewId": view_id, "direction": "callees", "group": "primary"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["functionId"] == function_id
    assert body["direction"] == "callees"
    assert body["group"] == "primary"
    assert body["callersSuppressed"] is False
    assert body["total"] >= 1
    for row in body["rows"]:
        assert row["isUtility"] is False
        assert "summaryStatus" in row
        assert "onCanvas" in row


@pytest.mark.asyncio
async def test_neighbour_rows_use_llm_name_when_no_analyst_rename(
    client: AsyncClient, session: AsyncSession, ingested: None
) -> None:
    """C13 auto-display: a neighbour row's `displayName` follows the
    `name_analyst ?? name_llm ?? name_ghidra` precedence, and `nameLlm` is
    exposed so the UI can badge the raw Ghidra name."""
    from sqlalchemy import update

    binary_id = await _get_binary_id(client, "acme.exe")
    function_id = await _get_function_id_by_name(client, binary_id, "main")
    view_id = await _get_view_id(session, binary_id)

    # Give one callee an LLM-proposed name directly (the worker path is
    # covered by test_summary_worker; this tests the read/display side).
    response = await client.get(
        f"/api/v1/functions/{function_id}/neighbours",
        params={"viewId": view_id, "direction": "callees", "group": "primary"},
    )
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert rows, "expected at least one callee row"
    target = rows[0]
    assert target["nameLlm"] is None  # nothing proposed yet

    await session.execute(
        update(Function).where(Function.id == target["id"]).values(name_llm="callee_proposed")
    )
    await session.commit()

    response = await client.get(
        f"/api/v1/functions/{function_id}/neighbours",
        params={"viewId": view_id, "direction": "callees", "group": "primary"},
    )
    updated = next(r for r in response.json()["rows"] if r["id"] == target["id"])
    assert updated["displayName"] == "callee_proposed"
    assert updated["nameLlm"] == "callee_proposed"
    assert updated["isRenamed"] is False


@pytest.mark.asyncio
async def test_dispatch_large_callees_are_capped_at_table_row_cap(
    client: AsyncClient, session: AsyncSession, ingested: None
) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    function_id = await _get_function_id_by_name(client, binary_id, "dispatch_large")
    view_id = await _get_view_id(session, binary_id)

    response = await client.get(
        f"/api/v1/functions/{function_id}/neighbours",
        params={"viewId": view_id, "direction": "callees", "group": "primary"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["rows"]) == 64  # table_row_cap default
    assert body["total"] >= 300


@pytest.mark.asyncio
async def test_big_hub_caller_table_is_suppressed(
    client: AsyncClient, session: AsyncSession, ingested: None
) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    function_id = await _get_function_id_by_name(client, binary_id, "mem_copy_block")
    view_id = await _get_view_id(session, binary_id)

    response = await client.get(
        f"/api/v1/functions/{function_id}/neighbours",
        params={"viewId": view_id, "direction": "callers", "group": "primary"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["callersSuppressed"] is True
    assert body["rows"] == []
    assert body["total"] >= 291


@pytest.mark.asyncio
async def test_dispatch_large_may_be_incomplete_true_for_callees(
    client: AsyncClient, session: AsyncSession, ingested: None
) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    function_id = await _get_function_id_by_name(client, binary_id, "dispatch_large")
    view_id = await _get_view_id(session, binary_id)

    response = await client.get(
        f"/api/v1/functions/{function_id}/neighbours",
        params={"viewId": view_id, "direction": "callees"},
    )
    assert response.json()["mayBeIncomplete"] is True


@pytest.mark.asyncio
async def test_get_neighbours_causes_no_summary_status_side_effects(
    client: AsyncClient, session: AsyncSession, ingested: None
) -> None:
    """C2c/Q23: the GET must never enqueue/mutate `summary_status`."""
    binary_id = await _get_binary_id(client, "acme.exe")
    function_id = await _get_function_id_by_name(client, binary_id, "main")
    view_id = await _get_view_id(session, binary_id)

    before = (await session.execute(select(Function.summary_status))).scalars().all()

    for _ in range(3):
        response = await client.get(
            f"/api/v1/functions/{function_id}/neighbours",
            params={"viewId": view_id, "direction": "callees"},
        )
        assert response.status_code == 200

    after = (await session.execute(select(Function.summary_status))).scalars().all()
    assert before == after
    assert all(status == "none" for status in after)


@pytest.mark.asyncio
async def test_utility_override_patch_moves_row_and_sets_analyst_source(
    client: AsyncClient, session: AsyncSession, ingested: None
) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    root_id = await _get_function_id_by_name(client, binary_id, "main")
    dispatcher_id = await _get_function_id_by_name(client, binary_id, "dispatch_small")
    view_id = await _get_view_id(session, binary_id)

    # `dispatch_small` (has fan_out=34, not high fan_in) is a plain "computed"
    # non-utility function to start with. Wire an edge from `main` to it via
    # ingestion data (already present because the mock adapter wires
    # structural roots into `main`), then use utility_override to force it
    # into the utility group and assert the neighbour page reflects it.
    patch_response = await client.patch(
        f"/api/v1/functions/{dispatcher_id}", json={"utilityOverride": "always"}
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["utilityOverride"] == "always"
    assert patch_response.json()["utilitySource"] == "analyst"

    utility_page = await client.get(
        f"/api/v1/functions/{root_id}/neighbours",
        params={"viewId": view_id, "direction": "callees", "group": "utility"},
    )
    utility_ids = {row["id"] for row in utility_page.json()["rows"]}
    assert dispatcher_id in utility_ids

    for row in utility_page.json()["rows"]:
        if row["id"] == dispatcher_id:
            assert row["utilitySource"] == "analyst"

    # Clearing the override moves it back.
    clear_response = await client.patch(
        f"/api/v1/functions/{dispatcher_id}", json={"utilityOverride": None}
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["utilityOverride"] is None
    assert clear_response.json()["utilitySource"] == "computed"


@pytest.mark.asyncio
async def test_patch_function_404_for_missing_function(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/functions/99999", json={"utilityOverride": "always"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FUNCTION_NOT_FOUND"
