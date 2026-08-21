"""`GET /binaries/{id}/views` — minimal read-only listing pulled forward from
I6 so I5's frontend can resolve a `viewId` for `GET /functions/{id}/neighbours`
(E2)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _get_binary_id(client: AsyncClient, name: str) -> int:
    binaries = (await client.get("/api/v1/binaries")).json()
    return next(b["id"] for b in binaries if b["name"] == name)


@pytest.mark.asyncio
async def test_list_views_returns_default_view_seeded_by_ingestion(
    client: AsyncClient, ingested: None
) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")

    response = await client.get(f"/api/v1/binaries/{binary_id}/views")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    view = body[0]
    assert view["name"] == "Default"
    assert view["binaryId"] == binary_id
    assert view["rootFunctionId"] is None
    assert "id" in view
    assert "createdAt" in view
    assert "updatedAt" in view


@pytest.mark.asyncio
async def test_list_views_404_for_missing_binary(client: AsyncClient) -> None:
    response = await client.get("/api/v1/binaries/99999/views")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BINARY_NOT_FOUND"
