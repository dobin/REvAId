"""GET /health (F4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_reports_db_ok_and_revision(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dbOk"] is True
    assert body["migrationRevision"] == "0015"
    assert body["viewerDbOk"] is True
    assert body["viewerMigrationRevision"] == "viewer_0002"
    assert body["ghidraAdapter"] == "mock"
    assert body["llmAdapter"] == "mock"
    # AM5: adapter reachability, not just the name — the mock adapter is
    # always reachable, so the default test app reports healthy.
    assert body["llmHealth"]["reachable"] is True
    assert body["llmHealth"]["detail"] is None


@pytest.mark.asyncio
async def test_health_reports_analysis_decompiler_status(
    client: AsyncClient, settings, tmp_path: Path
) -> None:
    executable = tmp_path / "kuna"
    executable.write_text("#!/bin/sh\necho 'Kuna 1.2.3'\n")
    executable.chmod(0o755)
    settings.decompiler_executable = str(executable)

    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["decompilerHealth"] == {
        "reachable": True,
        "detail": "Kuna 1.2.3",
    }
