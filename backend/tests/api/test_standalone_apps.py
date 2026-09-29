"""Standalone analysis-backend/viewer-backend startup boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from revaid.core.config import Settings as AnalysisSettings
from revaid.main import create_app as create_analysis_app
from revaid_ui.analysis.client import HttpAnalysisClient
from revaid_ui.core.config import Settings as ViewerSettings
from revaid_ui.main import create_app as create_viewer_app


async def _return_true() -> bool:
    return True


async def _return_binary(binary_id: int):
    from revaid_contracts.analysis import AnalysisBinary

    return AnalysisBinary(
        id=binary_id,
        name="sample.exe",
        version="1",
        analysis_image_base=None,
        function_count=0,
        edge_count=0,
        created_at="now",
    )


class EmptyViewerAnalysisClient:
    async def health(self) -> bool:
        return True

    async def get_binary(self, binary_id: int):
        return await _return_binary(binary_id)

    async def validate_function_membership(self, binary_id: int, function_ids: list[int]):
        return set(function_ids)

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_analysis_app_starts_with_only_analysis_database(
    settings: AnalysisSettings, migrated_db, viewer_db_path: Path
) -> None:
    assert viewer_db_path != Path(settings.db_path)
    assert not viewer_db_path.exists()
    app = create_analysis_app(settings)
    async with LifespanManager(app):
        assert hasattr(app.state, "session_factory")
        assert not hasattr(app.state, "viewer_session_factory")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://analysis"
        ) as client:
            response = await client.get("/api/v1/health")
            binaries_response = await client.get("/api/v1/binaries")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert binaries_response.status_code == 200
        assert binaries_response.json() == []
    assert not viewer_db_path.exists()


@pytest.mark.asyncio
async def test_viewer_app_starts_with_only_viewer_database(
    viewer_settings: ViewerSettings, viewer_migrated_db
) -> None:
    analysis_db_path = Path(viewer_settings.db_path)
    assert not analysis_db_path.exists()
    app = create_viewer_app(viewer_settings)
    app.state.analysis_client = EmptyViewerAnalysisClient()
    async with LifespanManager(app):
        assert not hasattr(app.state, "session_factory")
        assert hasattr(app.state, "viewer_session_factory")
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://viewer"
        ) as client:
            response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["viewerDbOk"] is True
    assert not analysis_db_path.exists()


@pytest.mark.asyncio
async def test_viewer_facade_uses_authenticated_analysis_api(
    settings: AnalysisSettings, viewer_settings: ViewerSettings, migrated_db, viewer_migrated_db
) -> None:
    analysis = create_analysis_app(settings)
    viewer = create_viewer_app(viewer_settings)
    async with (
        LifespanManager(analysis),
        AsyncClient(
            transport=ASGITransport(app=analysis), base_url="http://analysis-test"
        ) as analysis_http,
    ):
        viewer.state.analysis_client = HttpAnalysisClient(
            "http://analysis-test",
            token=viewer_settings.analysis_internal_token,
            client=analysis_http,
        )
        async with (
            LifespanManager(viewer),
            AsyncClient(transport=ASGITransport(app=viewer), base_url="http://viewer") as client,
        ):
            response = await client.get("/api/v1/binaries")
            internal = await client.get("/internal/v1/binaries")
            unauthenticated = await analysis_http.get("/internal/v1/binaries")
            authenticated = await analysis_http.get(
                "/internal/v1/binaries",
                headers={"Authorization": f"Bearer {viewer_settings.analysis_internal_token}"},
            )

    assert response.status_code == 200
    assert response.json() == []
    assert internal.status_code == 404
    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 200
    assert authenticated.json() == {"binaries": []}


@pytest.mark.asyncio
async def test_viewer_app_serves_facade_routes_without_analysis_session(
    viewer_settings: ViewerSettings, migrated_db, viewer_migrated_db
) -> None:
    app = create_viewer_app(viewer_settings)

    class StubAnalysis:
        async def health(self) -> bool:
            return await _return_true()

        async def health_details(self):
            return {"status": "ok", "decompiler_health": {"reachable": False}}

        async def get_binary(self, binary_id: int):
            return await _return_binary(binary_id)

        async def delete_binary(self, binary_id: int, confirm: str) -> bool:
            return confirm == "sample.exe"

        async def list_binaries(self):
            return [await _return_binary(101)]

        async def get_entry_points(self, binary_id: int):
            return []

        async def search_functions(
            self,
            binary_id: int,
            query: str | None,
            limit: int,
            offset: int,
            include_code: bool = False,
        ):
            return {
                "rows": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "query": query,
            }

        async def resolve_function_by_address(self, binary_id: int, address: int):
            return {}

        async def get_function_detail(self, function_id: int):
            return {}

        async def update_function(self, function_id: int, payload: dict[str, object]):
            return {}

        async def config(self):
            return {}

        async def get_llm_status(self):
            return {}

        async def probe_llm(self):
            return {}

        async def get_queue(self):
            return {}

        async def cancel_pending(self):
            return {}

        async def demand_summary(self, function_id: int, payload: dict[str, object]):
            return {}

        async def release_summary(self, function_id: int) -> None:
            return None

        async def regenerate_summary(self, function_id: int):
            return {}

        async def clear_binary_summaries(self, binary_id: int) -> None:
            return None

        async def import_upload(self, content, *, content_type: str, query=None):
            data = b"".join([chunk async for chunk in content])
            return {
                "job_id": "job-1",
                "phase": "queued",
                "bytes_received": len(data),
                "source_kind": (
                    "raw_binary" if content_type == "application/octet-stream" else "json_export"
                ),
            }

        async def get_import_status(self, job_id: str):
            return {
                "job_id": job_id,
                "phase": "queued",
                "bytes_received": 1,
                "source_kind": "json_export",
            }

        async def cancel_import(self, job_id: str):
            return {
                "job_id": job_id,
                "phase": "cancelled",
                "bytes_received": 1,
                "source_kind": "json_export",
            }

        async def validate_function_membership(
            self, binary_id: int, function_ids: list[int]
        ) -> set[int]:
            return set(function_ids)

        async def resolve_addresses(self, binary_id: int, addresses: list[int]):
            return {}

        async def get_featured_graph(self, binary_id: int):
            from revaid_contracts.analysis import FeaturedGraph

            return FeaturedGraph(functions=[], calls=[])

        async def find_canvas_origin(
            self, binary_id: int, function_id: int, candidate_ids: set[int]
        ):
            return None

        async def get_neighbours(self, query):
            from revaid_contracts.analysis import NeighbourPage

            return NeighbourPage(
                function_id=query.function_id,
                binary_id=101,
                anchor_has_indirect_calls=False,
                direction=query.direction,
                group=query.group,
                rows=[],
                total=0,
                total_primary=0,
                total_utility=0,
                limit=query.limit,
                offset=query.offset,
                callers_suppressed=False,
                may_be_incomplete=False,
            )

    app.state.analysis_client = StubAnalysis()  # type: ignore[assignment]
    async with (
        LifespanManager(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://viewer") as client,
    ):
        response = await client.get("/api/v1/binaries")
        upload = await client.post(
            "/api/v1/binaries/import",
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )
        status_response = await client.get("/api/v1/binaries/imports/job-1")
        cancel_response = await client.delete("/api/v1/binaries/imports/job-1")
    assert response.status_code == 200
    assert upload.status_code == 202
    assert upload.json()["jobId"] == "job-1"
    assert status_response.status_code == 200
    assert cancel_response.json()["phase"] == "cancelled"
