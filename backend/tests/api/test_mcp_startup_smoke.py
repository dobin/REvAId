"""Process-level smoke test for standalone Streamable HTTP MCP startup."""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


async def _wait_for_server(process: subprocess.Popen[bytes], port: int) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 30
    while loop.time() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"MCP server exited early with status {process.returncode}")
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port), timeout=0.25
            )
        except (OSError, TimeoutError):
            await asyncio.sleep(0.1)
            continue
        writer.close()
        await writer.wait_closed()
        return
    raise AssertionError("MCP server did not start listening within 30 seconds")


@pytest.mark.slow
@pytest.mark.asyncio
async def test_standalone_mcp_starts_and_advertises_analysis_tools(migrated_db: Path) -> None:
    port = _free_port()
    env = {
        **os.environ,
        "GRAPHREV_DB_PATH": str(migrated_db),
        "GRAPHREV_MCP_HOST": "127.0.0.1",
        "GRAPHREV_MCP_PORT": str(port),
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "revaid_mcp.server"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        await _wait_for_server(process, port)
        async with Client(f"http://127.0.0.1:{port}/mcp", mode="legacy") as client:
            tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "list_binaries",
            "find_functions",
            "search_code",
            "decompile_many",
            "get_function",
            "set_function_info",
        }
    finally:
        process.terminate()
        try:
            await asyncio.to_thread(process.wait, timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            await asyncio.to_thread(process.wait)
