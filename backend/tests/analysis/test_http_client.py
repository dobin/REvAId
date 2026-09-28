"""HTTP contract tests for the internal analysis client."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_ui.analysis.client import HttpAnalysisClient


@pytest.mark.asyncio
async def test_get_binary_uses_fixed_route_and_internal_bearer_token() -> None:
    app = FastAPI()
    observed: dict[str, str] = {}

    @app.get("/internal/v1/binaries/{binary_id}")
    async def get_binary(binary_id: int, request: Request) -> dict[str, object]:
        observed["path"] = request.url.path
        observed["authorization"] = request.headers["authorization"]
        return {
            "id": binary_id,
            "name": "sample.bin",
            "version": "1",
            "analysis_image_base": 4194304,
            "address_min": 4194304,
            "address_max": 4198400,
        }

    client = httpx.AsyncClient(
        base_url="http://analysis-test", transport=httpx.ASGITransport(app=app)
    )
    analysis = HttpAnalysisClient(
        "http://analysis-test", token="test-internal-token", client=client
    )
    binary = await analysis.get_binary(7)

    assert binary is not None and binary.id == 7
    assert observed == {
        "path": "/internal/v1/binaries/7",
        "authorization": "Bearer test-internal-token",
    }
    await analysis.aclose()


@pytest.mark.asyncio
async def test_analysis_client_maps_service_errors_to_bounded_app_error() -> None:
    app = FastAPI()

    @app.get("/internal/v1/binaries/{binary_id}")
    async def get_binary(binary_id: int) -> JSONResponse:
        return JSONResponse(status_code=500, content={"debug": "not forwarded"})

    client = httpx.AsyncClient(
        base_url="http://analysis-test", transport=httpx.ASGITransport(app=app)
    )
    analysis = HttpAnalysisClient("http://analysis-test", client=client)

    with pytest.raises(AppError) as exc_info:
        await analysis.get_binary(7)
    assert exc_info.value.code == ErrorCode.ANALYSIS_UNAVAILABLE
    assert exc_info.value.http_status == 503
    assert exc_info.value.details == {"status": 500}
    await analysis.aclose()


@pytest.mark.asyncio
async def test_analysis_client_rejects_oversized_response() -> None:
    app = FastAPI()

    @app.get("/internal/v1/binaries/{binary_id}")
    async def get_binary(binary_id: int) -> JSONResponse:
        return JSONResponse(
            content={
                "id": binary_id,
                "name": "x" * 200,
                "version": "1",
                "analysis_image_base": None,
            }
        )

    client = httpx.AsyncClient(
        base_url="http://analysis-test", transport=httpx.ASGITransport(app=app)
    )
    analysis = HttpAnalysisClient("http://analysis-test", max_response_bytes=64, client=client)

    with pytest.raises(AppError) as exc_info:
        await analysis.get_binary(7)
    assert exc_info.value.code == ErrorCode.ANALYSIS_UNAVAILABLE
    await analysis.aclose()


@pytest.mark.asyncio
async def test_analysis_client_treats_missing_binary_as_none() -> None:
    app = FastAPI()

    @app.get("/internal/v1/binaries/{binary_id}")
    async def get_binary(binary_id: int) -> JSONResponse:
        return JSONResponse(status_code=404, content={"internal": "details not forwarded"})

    client = httpx.AsyncClient(
        base_url="http://analysis-test", transport=httpx.ASGITransport(app=app)
    )
    analysis = HttpAnalysisClient("http://analysis-test", client=client)

    assert await analysis.get_binary(999) is None
    await analysis.aclose()


@pytest.mark.asyncio
async def test_analysis_client_streams_upload_and_forwards_fixed_query() -> None:
    app = FastAPI()
    observed: dict[str, object] = {}

    @app.post("/internal/v1/import-upload")
    async def import_upload(request: Request) -> dict[str, object]:
        observed["name"] = request.query_params.get("name")
        observed["version"] = request.query_params.get("version")
        observed["content_type"] = request.headers.get("content-type")
        observed["authorization"] = request.headers.get("authorization")
        observed["body"] = await request.body()
        return {
            "job_id": "job-1",
            "phase": "queued",
            "bytes_received": len(observed["body"]),
            "source_kind": "raw_binary",
        }

    client = httpx.AsyncClient(
        base_url="http://analysis-test", transport=httpx.ASGITransport(app=app)
    )
    analysis = HttpAnalysisClient("http://analysis-test", token="internal", client=client)

    async def chunks():
        yield b"first-"
        yield b"second"

    result = await analysis.import_upload(
        chunks(),
        content_type="application/octet-stream",
        query={"name": "sample.exe", "version": "1"},
    )

    assert result["job_id"] == "job-1"
    assert observed == {
        "name": "sample.exe",
        "version": "1",
        "content_type": "application/octet-stream",
        "authorization": "Bearer internal",
        "body": b"first-second",
    }
    await analysis.aclose()


@pytest.mark.asyncio
async def test_analysis_client_sanitizes_contract_mismatch() -> None:
    app = FastAPI()

    @app.get("/internal/v1/binaries/{binary_id}")
    async def get_binary(binary_id: int) -> dict[str, int]:
        return {"id": binary_id}

    client = httpx.AsyncClient(
        base_url="http://analysis-test", transport=httpx.ASGITransport(app=app)
    )
    analysis = HttpAnalysisClient("http://analysis-test", client=client)

    with pytest.raises(AppError) as exc_info:
        await analysis.get_binary(7)
    assert exc_info.value.code == ErrorCode.ANALYSIS_UNAVAILABLE
    assert "v1 contract" in exc_info.value.message
    await analysis.aclose()
