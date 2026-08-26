"""`/binaries/{id}/views`, `/views/{id}`, `/views/{id}/nodes` (TAD §4.2 #9-#12, I6)."""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient


async def _get_binary_id(client: AsyncClient, name: str) -> int:
    binaries = (await client.get("/api/v1/binaries")).json()
    return next(b["id"] for b in binaries if b["name"] == name)


async def _get_default_view_id(client: AsyncClient, binary_id: int) -> int:
    views = (await client.get(f"/api/v1/binaries/{binary_id}/views")).json()
    return int(views[0]["id"])


async def _get_two_entry_point_function_ids(client: AsyncClient, binary_id: int) -> tuple[int, int]:
    """Two distinct function ids in `binary_id` — any two, not necessarily
    entry points (the mock adapter only flags one `is_entry_point` function
    per binary); the search endpoint's default page always has >= 2 rows
    for `acme.exe`/`libparse.dll`."""
    body = (await client.get(f"/api/v1/binaries/{binary_id}/functions")).json()
    ids = [row["id"] for row in body["rows"]]
    assert len(ids) >= 2
    return ids[0], ids[1]


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


@pytest.mark.asyncio
async def test_create_view_and_get_view_round_trip(client: AsyncClient, ingested: None) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")

    create_response = await client.post(
        f"/api/v1/binaries/{binary_id}/views", json={"name": "crash path"}
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == "crash path"
    assert created["binaryId"] == binary_id
    assert created["camera"] == {"x": 0.0, "y": 0.0, "zoom": 1.0}
    assert created["nodes"] == []

    get_response = await client.get(f"/api/v1/views/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json() == created


@pytest.mark.asyncio
async def test_get_view_404_for_missing(client: AsyncClient) -> None:
    response = await client.get("/api/v1/views/99999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VIEW_NOT_FOUND"


@pytest.mark.asyncio
async def test_patch_view_name_root_and_camera(client: AsyncClient, ingested: None) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    view_id = await _get_default_view_id(client, binary_id)
    root_fn_id, _ = await _get_two_entry_point_function_ids(client, binary_id)

    response = await client.patch(
        f"/api/v1/views/{view_id}",
        json={
            "name": "crash path",
            "rootFunctionId": root_fn_id,
            "camera": {"x": -240.5, "y": 88.0, "zoom": 0.85},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "crash path"
    assert body["rootFunctionId"] == root_fn_id
    assert body["camera"] == {"x": -240.5, "y": 88.0, "zoom": 0.85}


@pytest.mark.asyncio
async def test_patch_view_waits_for_an_active_import_writer(
    client: AsyncClient, ingested: None
) -> None:
    """A view PATCH must queue behind ingestion, not fail with SQLITE_BUSY."""
    from graphrev.db.uow import write_lock

    binary_id = await _get_binary_id(client, "acme.exe")
    view_id = await _get_default_view_id(client, binary_id)

    async with write_lock():
        patch_task = asyncio.create_task(
            client.patch(f"/api/v1/views/{view_id}", json={"name": "queued update"})
        )
        await asyncio.sleep(0)
        assert not patch_task.done()

    response = await patch_task
    assert response.status_code == 200
    assert response.json()["name"] == "queued update"


@pytest.mark.asyncio
async def test_patch_view_root_function_id_can_be_set_back_to_null(
    client: AsyncClient, ingested: None
) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    view_id = await _get_default_view_id(client, binary_id)
    root_fn_id, _ = await _get_two_entry_point_function_ids(client, binary_id)

    await client.patch(f"/api/v1/views/{view_id}", json={"rootFunctionId": root_fn_id})
    response = await client.patch(f"/api/v1/views/{view_id}", json={"rootFunctionId": None})
    assert response.status_code == 200
    assert response.json()["rootFunctionId"] is None


@pytest.mark.asyncio
async def test_patch_view_404_for_missing(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/views/99999", json={"name": "x"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VIEW_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_only_view_is_forbidden(client: AsyncClient, ingested: None) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    view_id = await _get_default_view_id(client, binary_id)

    response = await client.delete(f"/api/v1/views/{view_id}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "LAST_VIEW_DELETE_FORBIDDEN"


@pytest.mark.asyncio
async def test_delete_view_succeeds_when_binary_has_another_view(
    client: AsyncClient, ingested: None
) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    default_view_id = await _get_default_view_id(client, binary_id)

    create_response = await client.post(
        f"/api/v1/binaries/{binary_id}/views", json={"name": "second"}
    )
    second_view_id = create_response.json()["id"]

    response = await client.delete(f"/api/v1/views/{second_view_id}")
    assert response.status_code == 204

    remaining = (await client.get(f"/api/v1/binaries/{binary_id}/views")).json()
    assert [v["id"] for v in remaining] == [default_view_id]


@pytest.mark.asyncio
async def test_duplicate_view_copies_nodes(client: AsyncClient, ingested: None) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    view_id = await _get_default_view_id(client, binary_id)
    root_fn_id, _ = await _get_two_entry_point_function_ids(client, binary_id)

    await client.patch(
        f"/api/v1/views/{view_id}/nodes",
        json={"upsert": [{"functionId": root_fn_id, "posX": 10.0, "originKind": "root"}]},
    )

    response = await client.post(f"/api/v1/views/{view_id}/duplicate")
    assert response.status_code == 201
    duplicated = response.json()
    assert duplicated["id"] != view_id
    assert duplicated["name"] == "Default (copy)"
    assert len(duplicated["nodes"]) == 1
    assert duplicated["nodes"][0]["functionId"] == root_fn_id
    assert duplicated["nodes"][0]["posX"] == 10.0


@pytest.mark.asyncio
async def test_set_last_view(client: AsyncClient, ingested: None) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    view_id = await _get_default_view_id(client, binary_id)

    response = await client.post(
        f"/api/v1/binaries/{binary_id}/last-view", json={"viewId": view_id}
    )
    assert response.status_code == 204

    binaries = (await client.get("/api/v1/binaries")).json()
    binary = next(b for b in binaries if b["id"] == binary_id)
    assert binary["lastViewId"] == view_id


@pytest.mark.asyncio
async def test_set_last_view_rejects_view_from_another_binary(
    client: AsyncClient, ingested: None
) -> None:
    acme_id = await _get_binary_id(client, "acme.exe")
    libparse_id = await _get_binary_id(client, "libparse.dll")
    libparse_view_id = await _get_default_view_id(client, libparse_id)

    response = await client.post(
        f"/api/v1/binaries/{acme_id}/last-view", json={"viewId": libparse_view_id}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_patch_view_nodes_upsert_and_remove_full_post_state(
    client: AsyncClient, ingested: None
) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    view_id = await _get_default_view_id(client, binary_id)
    root_fn_id, callee_fn_id = await _get_two_entry_point_function_ids(client, binary_id)

    response = await client.patch(
        f"/api/v1/views/{view_id}/nodes",
        json={
            "upsert": [
                {"functionId": root_fn_id, "posX": 120.0, "posY": 40.0, "pinned": True},
                {
                    "functionId": callee_fn_id,
                    "visible": True,
                    "originFunctionId": root_fn_id,
                    "originKind": "fanout",
                    "originImplied": False,
                },
            ]
        },
    )
    assert response.status_code == 200
    nodes = {n["functionId"]: n for n in response.json()["nodes"]}
    assert len(nodes) == 2
    assert nodes[root_fn_id]["posX"] == 120.0
    assert nodes[root_fn_id]["pinned"] is True
    assert nodes[callee_fn_id]["originFunctionId"] == root_fn_id
    assert nodes[callee_fn_id]["originKind"] == "fanout"

    # Second PATCH removes the callee — full post-state should only show root.
    remove_response = await client.patch(
        f"/api/v1/views/{view_id}/nodes", json={"remove": [callee_fn_id]}
    )
    assert remove_response.status_code == 200
    remaining_ids = {n["functionId"] for n in remove_response.json()["nodes"]}
    assert remaining_ids == {root_fn_id}


@pytest.mark.asyncio
async def test_patch_view_nodes_fanin_round_trips(client: AsyncClient, ingested: None) -> None:
    """A `fanin` node (leftward caller fan-out, D8b) persists like `fanout`."""
    binary_id = await _get_binary_id(client, "acme.exe")
    view_id = await _get_default_view_id(client, binary_id)
    root_fn_id, caller_fn_id = await _get_two_entry_point_function_ids(client, binary_id)

    response = await client.patch(
        f"/api/v1/views/{view_id}/nodes",
        json={
            "upsert": [
                {"functionId": root_fn_id, "originKind": "root"},
                {
                    "functionId": caller_fn_id,
                    "visible": True,
                    "originFunctionId": root_fn_id,
                    "originKind": "fanin",
                    "originImplied": False,
                },
            ]
        },
    )
    assert response.status_code == 200
    nodes = {n["functionId"]: n for n in response.json()["nodes"]}
    assert nodes[caller_fn_id]["originKind"] == "fanin"
    assert nodes[caller_fn_id]["originFunctionId"] == root_fn_id


@pytest.mark.asyncio
async def test_patch_view_nodes_rejects_fanin_without_origin_function_id(
    client: AsyncClient, ingested: None
) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    view_id = await _get_default_view_id(client, binary_id)
    fn_id, _ = await _get_two_entry_point_function_ids(client, binary_id)

    response = await client.patch(
        f"/api/v1/views/{view_id}/nodes",
        json={"upsert": [{"functionId": fn_id, "originKind": "fanin"}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_patch_view_nodes_rejects_fanout_without_origin_function_id(
    client: AsyncClient, ingested: None
) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    view_id = await _get_default_view_id(client, binary_id)
    fn_id, _ = await _get_two_entry_point_function_ids(client, binary_id)

    response = await client.patch(
        f"/api/v1/views/{view_id}/nodes",
        json={"upsert": [{"functionId": fn_id, "originKind": "fanout"}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_patch_view_nodes_rejects_root_with_origin_function_id(
    client: AsyncClient, ingested: None
) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    view_id = await _get_default_view_id(client, binary_id)
    fn_id, other_fn_id = await _get_two_entry_point_function_ids(client, binary_id)

    response = await client.patch(
        f"/api/v1/views/{view_id}/nodes",
        json={
            "upsert": [{"functionId": fn_id, "originKind": "root", "originFunctionId": other_fn_id}]
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_patch_view_nodes_404_for_missing_view(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/views/99999/nodes", json={"upsert": []})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VIEW_NOT_FOUND"


@pytest.mark.asyncio
async def test_patch_view_nodes_is_idempotent(client: AsyncClient, ingested: None) -> None:
    binary_id = await _get_binary_id(client, "acme.exe")
    view_id = await _get_default_view_id(client, binary_id)
    fn_id, _ = await _get_two_entry_point_function_ids(client, binary_id)

    payload = {"upsert": [{"functionId": fn_id, "posX": 5.0, "posY": 6.0}]}
    first = await client.patch(f"/api/v1/views/{view_id}/nodes", json=payload)
    second = await client.patch(f"/api/v1/views/{view_id}/nodes", json=payload)
    assert first.json() == second.json()
