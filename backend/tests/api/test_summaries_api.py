"""`/functions/{id}/summary*` (TAD §4.2 endpoints 17-19, I7 exit criteria)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _get_main_function_id(client: AsyncClient) -> int:
    binaries = (await client.get("/api/v1/binaries")).json()
    acme_id = next(b["id"] for b in binaries if b["name"] == "acme.exe")
    search = (
        await client.get(f"/api/v1/binaries/{acme_id}/functions", params={"q": "main"})
    ).json()
    return int(next(r["id"] for r in search["rows"] if r["displayName"] == "main"))


@pytest.mark.asyncio
async def test_demand_summary_returns_202_pending_immediately(
    client: AsyncClient, ingested: None
) -> None:
    """C5a: POST /summary never blocks on the LLM — it must return fast with
    `pending`, regardless of the (1-8s simulated) adapter latency."""
    function_id = await _get_main_function_id(client)

    response = await client.post(
        f"/api/v1/functions/{function_id}/summary", json={"priority": 0}
    )
    assert response.status_code == 202
    body = response.json()
    assert body["functionId"] == function_id
    assert body["summaryStatus"] == "pending"


@pytest.mark.asyncio
async def test_demand_summary_404_for_missing_function(client: AsyncClient) -> None:
    response = await client.post("/api/v1/functions/99999/summary", json={"priority": 0})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FUNCTION_NOT_FOUND"


@pytest.mark.asyncio
async def test_demand_summary_validation_error_for_bad_priority(
    client: AsyncClient, ingested: None
) -> None:
    function_id = await _get_main_function_id(client)
    response = await client.post(
        f"/api/v1/functions/{function_id}/summary", json={"priority": "not-an-int"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_demand_summary_validation_error_for_out_of_range_priority(
    client: AsyncClient, ingested: None
) -> None:
    """B4: an out-of-range priority must be rejected by request validation
    (422) *before* the row is ever flipped to `pending` — previously this
    reached `SummaryQueue.enqueue`'s own `ValueError` as an unhandled 500,
    after the DB write had already happened."""
    function_id = await _get_main_function_id(client)
    response = await client.post(
        f"/api/v1/functions/{function_id}/summary", json={"priority": 99}
    )
    assert response.status_code == 422

    # The row must not have been left dangling at `pending` by the rejected
    # request (it was never `demand_summary`'d successfully at all).
    detail = (await client.get(f"/api/v1/functions/{function_id}")).json()
    assert detail["summary"]["status"] != "pending"


@pytest.mark.asyncio
async def test_release_summary_demand_returns_204(client: AsyncClient, ingested: None) -> None:
    function_id = await _get_main_function_id(client)
    await client.post(f"/api/v1/functions/{function_id}/summary", json={"priority": 3})

    response = await client.delete(f"/api/v1/functions/{function_id}/summary")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_release_summary_demand_is_a_noop_for_unqueued_function(
    client: AsyncClient, ingested: None
) -> None:
    function_id = await _get_main_function_id(client)
    response = await client.delete(f"/api/v1/functions/{function_id}/summary")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_regenerate_summary_returns_202_pending(
    client: AsyncClient, ingested: None
) -> None:
    """C7: regenerate forces priority 0 and bypasses the cache check."""
    function_id = await _get_main_function_id(client)

    response = await client.post(f"/api/v1/functions/{function_id}/summary/regenerate")
    assert response.status_code == 202
    body = response.json()
    assert body["functionId"] == function_id
    assert body["summaryStatus"] == "pending"


@pytest.mark.asyncio
async def test_regenerate_summary_404_for_missing_function(client: AsyncClient) -> None:
    response = await client.post("/api/v1/functions/99999/summary/regenerate")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FUNCTION_NOT_FOUND"


@pytest.mark.asyncio
async def test_duplicate_demand_does_not_create_a_second_queue_item(
    client: AsyncClient, ingested: None
) -> None:
    """I7 exit test: a duplicate request creates no second queue item."""
    function_id = await _get_main_function_id(client)

    await client.post(f"/api/v1/functions/{function_id}/summary", json={"priority": 2})
    await client.post(f"/api/v1/functions/{function_id}/summary", json={"priority": 2})

    snapshot = (await client.get("/api/v1/queue")).json()
    occurrences = sum(
        1
        for row in (*snapshot["queued"], *snapshot["inFlight"])
        if row["functionId"] == function_id
    )
    assert occurrences == 1
