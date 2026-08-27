"""GET /config (E1d)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from graphrev.core.config import get_settings


@pytest.mark.asyncio
async def test_config_returns_camel_case_defaults(client: AsyncClient) -> None:
    response = await client.get("/api/v1/config")
    assert response.status_code == 200
    body = response.json()

    assert body["tableRowCap"] == 64
    assert body["callerSuppressThreshold"] == 32
    assert body["utilityFanInThreshold"] == 50
    assert body["fanOutAllHardCap"] == 50
    assert body["nodeCountSoftWarning"] == 150
    assert body["cardWidthPx"] == 440
    assert body["summaryConcurrency"] == 4
    assert body["summaryDemandDebounceMs"] == 250
    assert "red" in body["nodeColorPalette"]
    assert body["adapters"] == {"ghidra": "mock", "llm": "mock", "llmModel": "mock-llm-v1"}


@pytest.mark.asyncio
async def test_config_reflects_env_override(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GRAPHREV_TABLE_ROW_CAP", "8")
    get_settings.cache_clear()
    try:
        response = await client.get("/api/v1/config")
        assert response.json()["tableRowCap"] == 8
    finally:
        get_settings.cache_clear()
