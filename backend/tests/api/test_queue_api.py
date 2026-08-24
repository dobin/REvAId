"""`GET /queue`, `POST /queue/cancel-pending` (TAD §4.2 endpoints 20-21, E1c)."""

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
async def test_queue_snapshot_shape_when_empty(client: AsyncClient) -> None:
    response = await client.get("/api/v1/queue")
    assert response.status_code == 200
    body = response.json()
    assert body["queued"] == []
    assert body["inFlight"] == []
    assert body["queuedCount"] == 0
    assert body["inFlightCount"] == 0
    assert body["pausedUntil"] is None


@pytest.mark.asyncio
async def test_queue_snapshot_reflects_a_demanded_summary(
    client: AsyncClient, ingested: None
) -> None:
    function_id = await _get_main_function_id(client)
    await client.post(f"/api/v1/functions/{function_id}/summary", json={"priority": 1})

    response = await client.get("/api/v1/queue")
    body = response.json()
    ids = {row["functionId"] for row in (*body["queued"], *body["inFlight"])}
    assert function_id in ids
    assert body["queuedCount"] + body["inFlightCount"] >= 1


@pytest.mark.asyncio
async def test_cancel_pending_drops_queued_unstarted_items(
    client: AsyncClient, ingested: None
) -> None:
    function_id = await _get_main_function_id(client)
    await client.post(f"/api/v1/functions/{function_id}/summary", json={"priority": 3})

    response = await client.post("/api/v1/queue/cancel-pending")
    assert response.status_code == 200

    snapshot = (await client.get("/api/v1/queue")).json()
    queued_ids = {row["functionId"] for row in snapshot["queued"]}
    # The item may already be in-flight (picked up by a worker before the
    # cancel arrived) — cancel-pending never touches in-flight work (C8) —
    # but it must not still be sitting in the *queued* list.
    assert function_id not in queued_ids
