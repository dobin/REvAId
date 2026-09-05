"""Passive LLM worker status and explicit live probe endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from graphrev.repositories.llm_status import record_worker_outcome


@pytest.mark.asyncio
async def test_passive_status_reports_no_current_configuration_outcome(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/llm-status")
    assert response.status_code == 200
    assert response.json() == {
        "adapter": "mock",
        "model": "mock-llm-v1",
        "outcome": "no_outcome",
        "observedAt": None,
        "errorCode": None,
    }


@pytest.mark.asyncio
async def test_passive_status_returns_matching_durable_worker_outcome(
    client: AsyncClient,
) -> None:
    app = client._transport.app  # type: ignore[attr-defined]
    async with app.state.session_factory() as session:
        await record_worker_outcome(
            session,
            adapter="mock",
            model="mock-llm-v1",
            outcome="rate_limited",
            observed_at="2026-09-05T12:00:00+00:00",
            function_id=1,
            error_code="SUMMARY_RATE_LIMITED",
        )
        await session.commit()

    response = await client.get("/api/v1/llm-status")
    assert response.status_code == 200
    assert response.json() == {
        "adapter": "mock",
        "model": "mock-llm-v1",
        "outcome": "rate_limited",
        "observedAt": "2026-09-05T12:00:00+00:00",
        "errorCode": "SUMMARY_RATE_LIMITED",
    }


@pytest.mark.asyncio
async def test_explicit_probe_returns_adapter_health_without_persisting_status(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/v1/llm-status/probe")
    assert response.status_code == 200
    assert response.json() == {"reachable": True, "detail": None}

    status = await client.get("/api/v1/llm-status")
    assert status.json()["outcome"] == "no_outcome"