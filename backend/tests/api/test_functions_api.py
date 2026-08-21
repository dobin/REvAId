"""`GET /functions/{id}` (I3, E1)."""

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
async def test_get_function_returns_full_dto_shape(client: AsyncClient, ingested: None) -> None:
    function_id = await _get_main_function_id(client)

    response = await client.get(f"/api/v1/functions/{function_id}")
    assert response.status_code == 200
    body = response.json()

    assert body["id"] == function_id
    assert body["displayName"] == "main"
    assert body["nameGhidra"] == "main"
    assert body["nameAnalyst"] is None
    assert body["isRenamed"] is False
    assert isinstance(body["parameters"], list)
    assert body["kind"] == "normal"
    assert body["isEntryPoint"] is True
    assert body["utilitySource"] == "computed"
    assert body["calleeCount"] == body["fanOut"]
    assert body["callerCount"] == body["fanIn"]
    assert body["hasIndirectCalls"] is False

    summary = body["summary"]
    assert summary["status"] == "none"
    assert summary["short"] is None
    assert summary["isStale"] is False


@pytest.mark.asyncio
async def test_get_function_404_for_missing_function(client: AsyncClient) -> None:
    response = await client.get("/api/v1/functions/99999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "FUNCTION_NOT_FOUND"
