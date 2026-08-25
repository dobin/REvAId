"""GET /health (F4)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_reports_db_ok_and_revision(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dbOk"] is True
    assert body["migrationRevision"] == "0005"
    assert body["ghidraAdapter"] == "mock"
    assert body["llmAdapter"] == "mock"
    # AM5: adapter reachability, not just the name — the mock adapter is
    # always reachable, so the default test app reports healthy.
    assert body["llmHealth"]["reachable"] is True
    assert body["llmHealth"]["detail"] is None
