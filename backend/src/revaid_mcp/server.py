"""Streamable HTTP MCP server exposing GraphRev binary analysis data."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revaid.core.config import get_settings
from revaid.db.engine import create_engine, create_session_factory, dispose_engine
from revaid.db.uow import write_lock
from revaid.schemas.mcp import (
    McpBinaryListDto,
    McpFunctionDetailDto,
    McpFunctionSearchPageDto,
    McpFunctionUpdateDto,
)
from revaid.services.mcp_service import (
    find_mcp_functions,
    get_mcp_function,
    list_mcp_binaries,
    set_mcp_function_info,
)
from revaid_contracts.http_errors import AppError

mcp = MCPServer("GraphRev", version="0.1.0")
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _sessions() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("GraphRev MCP database is not initialized")
    return _session_factory


def _tool_error(exc: AppError) -> ToolError:
    details = f" Details: {exc.details}" if exc.details else ""
    return ToolError(f"{exc.code}: {exc.message}{details}")


@mcp.tool()
async def list_binaries() -> McpBinaryListDto:
    """List available binaries and their versions, function counts, and edge counts."""
    async with _sessions()() as session:
        return await list_mcp_binaries(session)


@mcp.tool()
async def find_functions(
    binary_name: str,
    binary_version: str = "",
    query: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> McpFunctionSearchPageDto:
    """Find functions in one binary by name, address, notes, or decompiled C content."""
    settings = get_settings()
    try:
        async with _sessions()() as session:
            return await find_mcp_functions(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                query=query,
                limit=limit,
                offset=offset,
                max_limit=settings.function_search_max_limit,
            )
    except AppError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
async def get_function(
    binary_name: str,
    binary_version: str = "",
    function_id: int | None = None,
    address: int | str | None = None,
    name: str | None = None,
    include_assembly: bool = False,
    include_decompile: bool = True,
) -> McpFunctionDetailDto:
    """Return decompiled C, metadata, callers, and callees for one function.

    Specify exactly one selector: function_id, exact start address (integer,
    decimal string, or 0x-prefixed hex string), or an exact stored name.
    Ambiguous names must be retried with id or address.
    Set include_assembly to true to include disassembly (asm) in the result.
    Set include_decompile to false to omit decompiled C from the result.
    Prefer the decompiled C for most use cases; it is more compact and easier to
    parse than the assembly.
    """
    try:
        async with _sessions()() as session:
            return await get_mcp_function(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                function_id=function_id,
                address=address,
                name=name,
                include_assembly=include_assembly,
                include_decompile=include_decompile,
            )
    except AppError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
async def set_function_info(
    binary_name: str,
    binary_version: str = "",
    function_id: int | None = None,
    address: int | str | None = None,
    name: str | None = None,
    name_llm: str | None = None,
    summary_short: str | None = None,
    summary_long: str | None = None,
) -> McpFunctionUpdateDto:
    """Set an analyzed function's LLM name and/or summaries.

    Specify exactly one function selector. Only non-null information fields are
    updated; omitted fields retain their current values. A successful update
    marks the summary ready.
    """
    try:
        async with write_lock(), _sessions()() as session:
            return await set_mcp_function_info(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                function_id=function_id,
                address=address,
                name=name,
                name_llm=name_llm,
                summary_short=summary_short,
                summary_long=summary_long,
            )
    except AppError as exc:
        raise _tool_error(exc) from exc


def main() -> None:
    """Run GraphRev MCP on its configured loopback Streamable HTTP endpoint."""
    global _session_factory

    settings = get_settings()
    engine = create_engine(settings)
    _session_factory = create_session_factory(engine)
    try:
        mcp.run(
            transport="streamable-http",
            host=settings.mcp_host,
            port=settings.mcp_port,
            streamable_http_path="/mcp",
        )
    finally:
        import asyncio

        asyncio.run(dispose_engine(engine))
        _session_factory = None


if __name__ == "__main__":
    main()
