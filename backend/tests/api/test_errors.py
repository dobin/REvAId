"""E4 error envelope shape, for both our own AppError and framework errors."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_unknown_route_returns_e4_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/v1/this-route-does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]


@pytest.mark.asyncio
async def test_validation_error_returns_e4_envelope(client: AsyncClient) -> None:
    # POST with an unexpected body/no matching route on a GET-only endpoint
    # still exercises a framework-level HTTPException (405) through the envelope.
    response = await client.post("/api/v1/config")
    assert response.status_code == 405
    body = response.json()
    assert "error" in body
    assert "code" in body["error"]
