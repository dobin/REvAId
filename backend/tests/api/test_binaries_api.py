"""`GET /binaries`, `DELETE /binaries/{id}`, `GET /binaries/{id}/entry-points`,
`GET /binaries/{id}/functions` (search), `GET /binaries/{id}/functions/by-address`
(I3, E1, E1a, E1b, D2)."""

from __future__ import annotations

import asyncio
import json

import pytest
from httpx import AsyncClient

from graphrev.core.config import Settings, get_settings


@pytest.mark.asyncio
async def test_list_binaries_returns_both_mock_binaries_with_counts(
    client: AsyncClient, ingested: None
) -> None:
    response = await client.get("/api/v1/binaries")
    assert response.status_code == 200
    body = response.json()
    names = {b["name"] for b in body}
    assert names == {"acme.exe", "libparse.dll"}
    for b in body:
        assert b["functionCount"] > 0
        assert b["edgeCount"] > 0
        assert "lastViewId" in b
        assert "createdAt" in b
        assert b["analysisImageBase"] is None


@pytest.mark.asyncio
async def test_list_binaries_empty_when_nothing_ingested(client: AsyncClient) -> None:
    response = await client.get("/api/v1/binaries")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_binaries_redacts_last_view_id_in_public_mode(
    client: AsyncClient, ingested: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    binaries = (await client.get("/api/v1/binaries")).json()
    acme_id = next(b["id"] for b in binaries if b["name"] == "acme.exe")
    views = (await client.get(f"/api/v1/binaries/{acme_id}/views")).json()
    view_id = views[0]["id"]

    # Persist a last-view pointer in private mode first.
    await client.post(f"/api/v1/binaries/{acme_id}/last-view", json={"viewId": view_id})
    body = (await client.get("/api/v1/binaries")).json()
    assert next(b for b in body if b["name"] == "acme.exe")["lastViewId"] == view_id

    # ADR 0006: in public mode the pointer is redacted so it cannot leak.
    monkeypatch.setenv("GRAPHREV_PUBLIC_MODE", "true")
    get_settings.cache_clear()
    try:
        body = (await client.get("/api/v1/binaries")).json()
        assert all(b["lastViewId"] is None for b in body)
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_get_entry_points_returns_main_for_acme_exe(
    client: AsyncClient, ingested: None
) -> None:
    binaries = (await client.get("/api/v1/binaries")).json()
    acme_id = next(b["id"] for b in binaries if b["name"] == "acme.exe")

    response = await client.get(f"/api/v1/binaries/{acme_id}/entry-points")
    assert response.status_code == 200
    body = response.json()
    assert len(body["entryPoints"]) <= 5
    names = {ep["displayName"] for ep in body["entryPoints"]}
    assert "main" in names


@pytest.mark.asyncio
async def test_get_entry_points_404_for_missing_binary(client: AsyncClient) -> None:
    response = await client.get("/api/v1/binaries/99999/entry-points")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BINARY_NOT_FOUND"


@pytest.mark.asyncio
async def test_search_functions_by_substring(client: AsyncClient, ingested: None) -> None:
    binaries = (await client.get("/api/v1/binaries")).json()
    acme_id = next(b["id"] for b in binaries if b["name"] == "acme.exe")

    response = await client.get(f"/api/v1/binaries/{acme_id}/functions", params={"q": "parse"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert all("parse" in row["displayName"].lower() for row in body["rows"])
    assert body["query"] == "parse"


@pytest.mark.asyncio
async def test_search_functions_paginates(client: AsyncClient, ingested: None) -> None:
    binaries = (await client.get("/api/v1/binaries")).json()
    acme_id = next(b["id"] for b in binaries if b["name"] == "acme.exe")

    page1 = (
        await client.get(f"/api/v1/binaries/{acme_id}/functions", params={"limit": 5, "offset": 0})
    ).json()
    page2 = (
        await client.get(f"/api/v1/binaries/{acme_id}/functions", params={"limit": 5, "offset": 5})
    ).json()
    assert len(page1["rows"]) == 5
    assert len(page2["rows"]) == 5
    ids1 = {r["id"] for r in page1["rows"]}
    ids2 = {r["id"] for r in page2["rows"]}
    assert ids1.isdisjoint(ids2)
    assert page1["total"] == page2["total"]


@pytest.mark.asyncio
async def test_search_functions_404_for_missing_binary(client: AsyncClient) -> None:
    response = await client.get("/api/v1/binaries/99999/functions")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BINARY_NOT_FOUND"


@pytest.mark.asyncio
async def test_resolve_function_by_address_exact_hit(client: AsyncClient, ingested: None) -> None:
    binaries = (await client.get("/api/v1/binaries")).json()
    acme_id = next(b["id"] for b in binaries if b["name"] == "acme.exe")

    response = await client.get(
        f"/api/v1/binaries/{acme_id}/functions/by-address", params={"address": "0x401000"}
    )
    assert response.status_code == 200
    assert response.json()["displayName"] == "main"


@pytest.mark.asyncio
async def test_resolve_function_by_address_mid_range_hit(
    client: AsyncClient, ingested: None
) -> None:
    binaries = (await client.get("/api/v1/binaries")).json()
    acme_id = next(b["id"] for b in binaries if b["name"] == "acme.exe")

    # `main` is at 0x00401000; the mock adapter allocates addresses in 0x20
    # steps, so a mid-range offset (+0x10) still resolves to `main`.
    response = await client.get(
        f"/api/v1/binaries/{acme_id}/functions/by-address", params={"address": "0x401010"}
    )
    assert response.status_code == 200
    assert response.json()["displayName"] == "main"


@pytest.mark.asyncio
async def test_resolve_function_by_address_unresolved(client: AsyncClient, ingested: None) -> None:
    binaries = (await client.get("/api/v1/binaries")).json()
    acme_id = next(b["id"] for b in binaries if b["name"] == "acme.exe")

    response = await client.get(
        f"/api/v1/binaries/{acme_id}/functions/by-address", params={"address": "0x100"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ADDRESS_UNRESOLVED"


@pytest.mark.asyncio
async def test_delete_binary_requires_confirmation(client: AsyncClient, ingested: None) -> None:
    binaries = (await client.get("/api/v1/binaries")).json()
    acme_id = next(b["id"] for b in binaries if b["name"] == "acme.exe")

    response = await client.delete(
        f"/api/v1/binaries/{acme_id}", params={"confirm": "not-the-name"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "CONFIRMATION_MISMATCH"


@pytest.mark.asyncio
async def test_delete_binary_succeeds_with_correct_confirmation(
    client: AsyncClient, ingested: None
) -> None:
    binaries = (await client.get("/api/v1/binaries")).json()
    acme_id = next(b["id"] for b in binaries if b["name"] == "acme.exe")

    response = await client.delete(f"/api/v1/binaries/{acme_id}", params={"confirm": "acme.exe"})
    assert response.status_code == 204

    remaining = (await client.get("/api/v1/binaries")).json()
    assert acme_id not in {b["id"] for b in remaining}


@pytest.mark.asyncio
async def test_delete_binary_404_for_missing_binary(client: AsyncClient) -> None:
    response = await client.delete("/api/v1/binaries/99999", params={"confirm": "anything"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BINARY_NOT_FOUND"


def _import_document() -> dict:
    """A minimal Ghidra export document (schema v1) for the import endpoint."""
    return {
        "schemaVersion": 1,
        "binary": {
            "name": "imported.exe",
            "version": "2.0",
            "sourcePath": "/tmp/imported.exe",
            "analysisImageBase": 0x400000,
        },
        "functions": [
            {
                "address": 0x401000,
                "name": "main",
                "parameters": [{"ordinal": 0, "name": "argc", "type": "int"}],
                "signature": "int main(int argc)",
                "assembly": "00401000  PUSH RBP",
                "codeC": "int main(int argc){return 0;}",
                "kind": "normal",
                "isEntryPoint": True,
            },
            {
                "address": 0x401100,
                "name": "helper",
                "parameters": [],
                "signature": "void helper(void)",
                "assembly": "00401100  RET",
                "codeC": "void helper(void){}",
                "kind": "normal",
            },
        ],
        "edges": [{"callerAddress": 0x401000, "calleeAddress": 0x401100}],
    }


async def _wait_for_import(client: AsyncClient, job_id: str) -> dict:
    """Wait briefly for an in-process job in an ASGI integration test."""
    for _ in range(100):
        body = (await client.get(f"/api/v1/binaries/imports/{job_id}")).json()
        if body["phase"] in {"completed", "failed", "cancelled"}:
            return body
        await asyncio.sleep(0.01)
    raise AssertionError("import job did not reach a terminal state")


async def _submit_import(client: AsyncClient, document: dict) -> dict:
    response = await client.post(
        "/api/v1/binaries/import",
        content=json.dumps(document),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 202
    return await _wait_for_import(client, response.json()["jobId"])


@pytest.mark.asyncio
async def test_import_binary_creates_new_binary(client: AsyncClient) -> None:
    body = await _submit_import(client, _import_document())
    assert body["phase"] == "completed"
    result = body["result"]
    assert result is not None
    assert result["name"] == "imported.exe"
    assert result["version"] == "2.0"
    assert result["functionsInserted"] == 2
    assert result["edgesInserted"] == 1

    listing = (await client.get("/api/v1/binaries")).json()
    names = {b["name"] for b in listing}
    assert "imported.exe" in names
    imported = next(b for b in listing if b["name"] == "imported.exe")
    assert imported["analysisImageBase"] == 0x400000


@pytest.mark.asyncio
async def test_import_binary_is_idempotent(client: AsyncClient) -> None:
    first_status = await _submit_import(client, _import_document())
    second_status = await _submit_import(client, _import_document())
    first = first_status["result"]
    second = second_status["result"]

    assert first is not None
    assert second is not None
    assert second["binaryId"] == first["binaryId"]
    assert second["functionsInserted"] == 0
    assert second["functionsUpdated"] > 0

    listing = (await client.get("/api/v1/binaries")).json()
    assert len([b for b in listing if b["name"] == "imported.exe"]) == 1


@pytest.mark.asyncio
async def test_import_binary_rejects_unsupported_schema(client: AsyncClient) -> None:
    doc = _import_document()
    doc["schemaVersion"] = 999
    body = await _submit_import(client, doc)
    assert body["phase"] == "failed"
    assert "schemaVersion" in body["errorMessage"]


@pytest.mark.asyncio
async def test_import_binary_rejects_malformed_body(client: AsyncClient) -> None:
    body = await _submit_import(client, {"not": "an export"})
    assert body["phase"] == "failed"


@pytest.mark.asyncio
async def test_import_binary_rejects_oversized_stream(
    client: AsyncClient, settings: Settings
) -> None:
    # The client and app share the cached test settings; constrain it so this
    # verifies the in-stream cap rather than only Content-Length preflight.
    settings.import_max_upload_bytes = 8
    response = await client.post(
        "/api/v1/binaries/import",
        content=b'{"large": true}',
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMPORT_TOO_LARGE"


@pytest.mark.asyncio
async def test_import_status_404_for_unknown_job(client: AsyncClient) -> None:
    response = await client.get("/api/v1/binaries/imports/not-a-job")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "IMPORT_JOB_NOT_FOUND"
