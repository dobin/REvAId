"""`GET /functions/{id}` (I3, E1)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _get_main_function_id(client: AsyncClient) -> int:
    binaries = (await client.get("/api/v1/binaries")).json()
    acme_id = next(b["id"] for b in binaries if b["name"] == "acme.exe")
    search = (
        await client.get(f"/api/v1/binaries/{acme_id}/functions", params={"q": "main"})
    ).json()
    return int(next(r["id"] for r in search["rows"] if r["displayName"] == "main"))


@pytest.mark.asyncio
async def test_get_function_returns_full_dto_shape(client: AsyncClient, ingested: None) -> None:
    function_id = await _get_main_function_id(client)

    response = await client.get(f"/api/v1/functions/{function_id}")
    assert response.status_code == 200
    body = response.json()

    assert body["id"] == function_id
    assert body["displayName"] == "main"
    assert body["nameGhidra"] == "main"
    assert body["nameAnalyst"] is None
    assert body["isRenamed"] is False
    assert isinstance(body["parameters"], list)
    assert body["assembly"] == "; disassembly of main"
    assert body["codeC"] == "int main(int arg0) { return arg0; }"
    assert body["kind"] == "normal"
    assert body["isEntryPoint"] is True
    assert body["utilitySource"] == "computed"
    assert body["calleeCount"] == body["fanOut"]
    assert body["callerCount"] == body["fanIn"]
    assert body["hasIndirectCalls"] is False

    summary = body["summary"]
    assert summary["status"] == "none"
    assert summary["short"] is None
    assert summary["isStale"] is False


@pytest.mark.asyncio
async def test_get_function_404_for_missing_function(client: AsyncClient) -> None:
    response = await client.get("/api/v1/functions/99999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "FUNCTION_NOT_FOUND"


@pytest.mark.asyncio
async def test_display_name_precedence_analyst_beats_llm_beats_ghidra(
    client: AsyncClient, session: AsyncSession, ingested: None
) -> None:
    """C13 auto-display: `displayName` is `name_analyst ?? name_llm ??
    name_ghidra`, and neither stored name is overwritten. Verified through
    the public API on one function across all three states."""
    from sqlalchemy import update

    from graphrev.db.models import Function

    function_id = await _get_main_function_id(client)

    async def _refreshed() -> dict:
        return (await client.get(f"/api/v1/functions/{function_id}")).json()

    # State 1: no analyst name, no LLM name -> Ghidra name.
    body = await _refreshed()
    assert body["displayName"] == "main"
    assert body["nameLlm"] is None

    # State 2: LLM proposes a name -> it becomes the display name.
    await session.execute(
        update(Function).where(Function.id == function_id).values(name_llm="program_bootstrap")
    )
    await session.commit()
    body = await _refreshed()
    assert body["displayName"] == "program_bootstrap"
    assert body["nameLlm"] == "program_bootstrap"
    assert body["nameGhidra"] == "main"  # never overwritten
    assert body["isRenamed"] is False  # analyst rename is still what counts

    # State 3: analyst renames -> analyst beats the LLM proposal.
    await session.execute(
        update(Function).where(Function.id == function_id).values(name_analyst="entry")
    )
    await session.commit()
    body = await _refreshed()
    assert body["displayName"] == "entry"
    assert body["nameLlm"] == "program_bootstrap"  # still exposed, not overwritten
    assert body["isRenamed"] is True
