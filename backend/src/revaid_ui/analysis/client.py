"""Bounded HTTP client for the internal versioned analysis API."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from revaid_contracts.analysis import (
    AddressResolutionResponse,
    AnalysisBinary,
    AnalysisClient,
    AnalysisFunction,
    CanvasOrigin,
    CanvasOriginRequest,
    FeaturedGraph,
    FunctionMembership,
    FunctionMembershipRequest,
    NeighbourPage,
    NeighbourQuery,
    ResolvedFunction,
)
from revaid_contracts.http_errors import AppError, ErrorCode

ModelT = TypeVar("ModelT", bound=BaseModel)


class HttpAnalysisClient(AnalysisClient):
    """Internal client using a configured base URL, fixed paths, and finite bounds."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 5.0,
        max_response_bytes: int = 4 * 1024 * 1024,
        token: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_seconds)
        self._max_response_bytes = max_response_bytes
        self._token = token
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            follow_redirects=False,
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def get_binary(self, binary_id: int) -> AnalysisBinary | None:
        payload = await self._request("GET", f"/internal/v1/binaries/{binary_id}", missing_ok=True)
        return None if payload is None else self._validate(AnalysisBinary, payload)

    async def list_binaries(self) -> list[AnalysisBinary]:
        payload = await self._request("GET", "/internal/v1/binaries")
        assert payload is not None
        rows = payload.get("binaries")
        if not isinstance(rows, list):
            raise AppError(ErrorCode.ANALYSIS_UNAVAILABLE, "Invalid analysis binary list response.")
        return [self._validate(AnalysisBinary, row) for row in rows if isinstance(row, dict)]

    async def get_entry_points(self, binary_id: int) -> list[AnalysisFunction]:
        payload = await self._request("GET", f"/internal/v1/binaries/{binary_id}/entry-points")
        assert payload is not None
        rows = payload.get("functions")
        if not isinstance(rows, list):
            raise AppError(ErrorCode.ANALYSIS_UNAVAILABLE, "Invalid analysis entry-point response.")
        return [self._validate(AnalysisFunction, row) for row in rows if isinstance(row, dict)]

    async def delete_binary(self, binary_id: int, confirm: str) -> bool:
        response = await self._request(
            "DELETE",
            f"/internal/v1/binaries/{binary_id}",
            json_body={"confirm": confirm},
            missing_ok=True,
        )
        return response is not None

    async def search_functions(
        self,
        binary_id: int,
        query: str | None,
        limit: int,
        offset: int,
        include_code: bool = False,
    ) -> dict[str, Any]:
        payload = await self._request(
            "GET",
            f"/internal/v1/binaries/{binary_id}/functions",
            params={
                "q": query,
                "limit": str(limit),
                "offset": str(offset),
                "include_code": str(include_code).lower(),
            },
        )
        assert payload is not None
        return payload

    async def resolve_function_by_address(self, binary_id: int, address: int) -> dict[str, Any]:
        payload = await self._request(
            "POST",
            f"/internal/v1/binaries/{binary_id}/function-by-address",
            json_body={"address": address},
        )
        assert payload is not None
        return payload

    async def get_function_detail(self, function_id: int) -> dict[str, Any]:
        payload = await self._request("GET", f"/internal/v1/functions/{function_id}")
        assert payload is not None
        return payload

    async def update_function(self, function_id: int, payload: dict[str, object]) -> dict[str, Any]:
        response = await self._request(
            "PATCH", f"/internal/v1/functions/{function_id}", json_body=payload
        )
        assert response is not None
        return response

    async def get_llm_status(self) -> dict[str, Any]:
        payload = await self._request("GET", "/internal/v1/llm-status")
        assert payload is not None
        return payload

    async def probe_llm(self) -> dict[str, Any]:
        payload = await self._request("POST", "/internal/v1/llm-status/probe")
        assert payload is not None
        return payload

    async def demand_summary(self, function_id: int, payload: dict[str, object]) -> dict[str, Any]:
        response = await self._request(
            "POST", f"/internal/v1/functions/{function_id}/summary", json_body=payload
        )
        assert response is not None
        return response

    async def release_summary(self, function_id: int) -> None:
        await self._request("DELETE", f"/internal/v1/functions/{function_id}/summary")

    async def regenerate_summary(self, function_id: int) -> dict[str, Any]:
        response = await self._request(
            "POST", f"/internal/v1/functions/{function_id}/summary/regenerate"
        )
        assert response is not None
        return response

    async def clear_binary_summaries(self, binary_id: int) -> None:
        await self._request("DELETE", f"/internal/v1/binaries/{binary_id}/summaries")

    async def import_export(self, payload: dict[str, object]) -> dict[str, Any]:
        response = await self._request(
            "POST", "/internal/v1/binaries/import-export", json_body=payload
        )
        assert response is not None
        return response

    async def import_upload(
        self,
        content: AsyncIterator[bytes],
        *,
        content_type: str,
        query: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            "/internal/v1/import-upload",
            content=content,
            content_type=content_type,
            params=query,
        )
        assert response is not None
        return response

    async def get_import_status(self, job_id: str) -> dict[str, Any]:
        payload = await self._request("GET", f"/internal/v1/imports/{job_id}")
        assert payload is not None
        return payload

    async def cancel_import(self, job_id: str) -> dict[str, Any]:
        payload = await self._request("DELETE", f"/internal/v1/imports/{job_id}")
        assert payload is not None
        return payload

    async def health(self) -> bool:
        payload = await self._request("GET", "/internal/v1/health")
        return payload is not None and payload.get("status") == "ok"

    async def health_details(self) -> dict[str, object]:
        payload = await self._request("GET", "/internal/v1/health")
        if payload is None:
            return {"status": "unavailable"}
        decompiler_health = payload.get("decompiler_health")
        if not isinstance(decompiler_health, dict):
            payload["decompiler_health"] = {
                "reachable": False,
                "detail": "Analysis service did not report decompiler health.",
            }
        return payload

    async def config(self) -> dict[str, Any]:
        payload = await self._request("GET", "/internal/v1/config")
        assert payload is not None
        return payload

    async def migration_revision(self) -> str | None:
        payload = await self._request("GET", "/internal/v1/migration")
        return str(payload["revision"]) if payload is not None and "revision" in payload else None

    async def get_queue(self) -> dict[str, Any]:
        payload = await self._request("GET", "/internal/v1/queue")
        assert payload is not None
        return payload

    async def cancel_pending(self) -> dict[str, Any]:
        payload = await self._request("POST", "/internal/v1/queue/cancel-pending")
        assert payload is not None
        return payload

    async def get_function(self, function_id: int) -> AnalysisFunction | None:
        payload = await self._request(
            "GET", f"/internal/v1/functions/{function_id}", missing_ok=True
        )
        return None if payload is None else self._validate(AnalysisFunction, payload)

    async def validate_function_membership(
        self, binary_id: int, function_ids: list[int]
    ) -> set[int]:
        payload = FunctionMembershipRequest(function_ids=function_ids).model_dump(mode="json")
        response = await self._request(
            "POST", f"/internal/v1/binaries/{binary_id}/functions/membership", json_body=payload
        )
        assert response is not None
        return set(self._validate(FunctionMembership, response).valid_ids)

    async def resolve_addresses(
        self, binary_id: int, addresses: list[int]
    ) -> dict[int, ResolvedFunction | None]:
        response = await self._request(
            "POST",
            f"/internal/v1/binaries/{binary_id}/functions/resolve",
            json_body={"addresses": addresses},
        )
        assert response is not None
        parsed = self._validate(AddressResolutionResponse, response)
        return {
            row.address: (
                row.containing_function if row.containing_function is not None else row.function
            )
            for row in parsed.results
        }

    async def get_featured_graph(self, binary_id: int) -> FeaturedGraph:
        payload = await self._request("GET", f"/internal/v1/binaries/{binary_id}/featured-graph")
        assert payload is not None
        return self._validate(FeaturedGraph, payload)

    async def find_canvas_origin(
        self, binary_id: int, function_id: int, candidate_ids: set[int]
    ) -> tuple[int, str] | None:
        response = await self._request(
            "POST",
            "/internal/v1/functions/canvas-origin",
            json_body=CanvasOriginRequest(
                binary_id=binary_id,
                function_id=function_id,
                candidate_ids=sorted(candidate_ids),
            ).model_dump(mode="json"),
        )
        if response is None:
            return None
        origin = self._validate(CanvasOrigin, response)
        if origin.origin_function_id is None:
            return None
        return origin.origin_function_id, origin.origin_kind

    async def get_neighbours(self, query: NeighbourQuery) -> NeighbourPage:
        payload = await self._request(
            "POST", "/internal/v1/neighbours", json_body=query.model_dump(mode="json")
        )
        assert payload is not None
        return self._validate(NeighbourPage, payload)

    @staticmethod
    def _validate(model: type[ModelT], payload: dict[str, Any]) -> ModelT:
        try:
            return model.model_validate(payload)
        except ValidationError as exc:
            raise AppError(
                ErrorCode.ANALYSIS_UNAVAILABLE,
                "The analysis service returned a response outside the v1 contract.",
            ) from exc

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str | None] | None = None,
        content: bytes | AsyncIterator[bytes] | None = None,
        content_type: str | None = None,
        missing_ok: bool = False,
    ) -> dict[str, Any] | None:
        try:
            assert self._client is not None
            request_path = path
            response = await self._send(
                self._client,
                method,
                request_path,
                json_body,
                params,
                content,
                content_type,
            )
        except httpx.HTTPError as exc:
            raise AppError(
                ErrorCode.ANALYSIS_UNAVAILABLE,
                "The analysis service is unavailable.",
                details={"reason": type(exc).__name__},
            ) from exc

        if missing_ok and response.status_code == 404:
            return None
        if not 200 <= response.status_code < 300:
            try:
                raw_error = response.json().get("error", {})
                error_payload = raw_error if isinstance(raw_error, dict) else {}
                code_value = error_payload.get("code", ErrorCode.ANALYSIS_UNAVAILABLE)
                code = ErrorCode(code_value)
                message = str(
                    error_payload.get(
                        "message", "The analysis service rejected the internal request."
                    )
                )
                details = error_payload.get("details")
                if not isinstance(details, dict):
                    details = None
            except (ValueError, TypeError):
                code = ErrorCode.ANALYSIS_UNAVAILABLE
                message = "The analysis service rejected the internal request."
                details = None
            mapped_status = 503 if response.status_code >= 500 else response.status_code
            raise AppError(
                code,
                message,
                details=details or {"status": response.status_code},
                http_status=mapped_status,
            )
        if response.status_code == 204:
            return {"deleted": True}
        try:
            payload = json.loads(response.content)
        except ValueError as exc:
            raise AppError(
                ErrorCode.ANALYSIS_UNAVAILABLE,
                "The analysis service returned invalid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise AppError(
                ErrorCode.ANALYSIS_UNAVAILABLE,
                "The analysis service returned an invalid response shape.",
            )
        return payload

    async def _send(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        params: dict[str, str | None] | None,
        content: bytes | AsyncIterator[bytes] | None = None,
        content_type: str | None = None,
    ) -> httpx.Response:
        query_params = {key: value for key, value in (params or {}).items() if value is not None}
        async with client.stream(
            method,
            path,
            json=body,
            content=content,
            params=query_params,
            headers={**self._headers(), **({"Content-Type": content_type} if content_type else {})},
        ) as response:
            if not 200 <= response.status_code < 300:
                content = await response.aread()
                return httpx.Response(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=content,
                    request=response.request,
                )
            chunks: list[bytes] = []
            size = 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > self._max_response_bytes:
                    raise AppError(
                        ErrorCode.ANALYSIS_UNAVAILABLE,
                        "The analysis service response exceeded the configured limit.",
                    )
                chunks.append(chunk)
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                content=b"".join(chunks),
                request=response.request,
            )
