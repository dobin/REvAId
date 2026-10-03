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
    McpCodeSearchPageDto,
    McpDataItemDetailDto,
    McpDataItemSearchPageDto,
    McpDataItemUpdateDto,
    McpDecompileManyDto,
    McpFunctionDataDto,
    McpFunctionDetailDto,
    McpFunctionsByDataPageDto,
    McpFunctionSearchPageDto,
    McpFunctionSelector,
    McpFunctionUpdateDto,
    McpGetFunctionsDto,
    McpRelatedByDataPageDto,
)
from revaid.services.mcp_service import (
    decompile_mcp_functions,
    find_mcp_functions,
    find_mcp_functions_by_data,
    find_mcp_related_by_data,
    get_mcp_data_item,
    get_mcp_function,
    get_mcp_function_data,
    get_mcp_functions,
    list_mcp_binaries,
    search_mcp_code,
    search_mcp_data,
    set_mcp_data_item_summary,
    set_mcp_function_info,
)
from revaid_contracts.http_errors import AppError

_INSTRUCTIONS = """\
GraphRev holds decompiled binaries (C, asm, call graph, PE data items) for
reverse engineering. Pass binary_name/binary_version exactly as list_binaries
reports them.

Typical workflow:
* find_functions_by_data for strings/imports (e.g.
   "CreateFileW", "http", "password") is usually the fastest route to relevant
   code; find_functions for names/addresses; search_code to grep C patterns.
* Read: get_function (C + callers/callees) to walk the call graph;
   decompile_many to read several functions cheaply.
* Record findings with set_function_info and set_data_item_summary so later
    work builds on them.

Names like FUN_xxxx / sub_xxxx are auto-generated and unanalyzed.
"""

mcp = MCPServer("GraphRev", version="0.1.0", instructions=_INSTRUCTIONS)
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
    case_insensitive: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> McpFunctionSearchPageDto:
    """Find functions by substring of any name (original/LLM/analyst), notes,
    address (decimal or hex), or decompiled C. Returns compact rows (no code).

    Use search_code instead when you need to see where in the C a pattern occurs.
    """
    settings = get_settings()
    try:
        async with _sessions()() as session:
            return await find_mcp_functions(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                query=query,
                case_insensitive=case_insensitive,
                limit=limit,
                offset=offset,
                max_limit=settings.function_search_max_limit,
            )
    except AppError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
async def search_code(
    binary_name: str,
    query: str,
    binary_version: str = "",
    case_insensitive: bool = True,
    context_lines: int = 3,
    limit: int = 20,
    offset: int = 0,
) -> McpCodeSearchPageDto:
    """Grep the decompiled C of one binary (case-insensitive by default).

    Literal substring (not regex). Returns, per matching function, only the
    matching lines plus context_lines (max 20) before and after, each with its
    1-based line number and is_match flag. Use get_function or decompile_many
    to read whole functions.
    """
    settings = get_settings()
    try:
        async with _sessions()() as session:
            return await search_mcp_code(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                query=query,
                case_insensitive=case_insensitive,
                context_lines=context_lines,
                limit=limit,
                offset=offset,
                max_limit=settings.function_search_max_limit,
            )
    except AppError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
async def decompile_many(
    binary_name: str,
    functions: list[McpFunctionSelector],
    binary_version: str = "",
) -> McpDecompileManyDto:
    """Return decompiled C for up to 20 functions in one call.

    Each entry in functions sets exactly one of function_id, address (integer,
    decimal string, or 0x-hex string), or name.
    Cheaper than get_functions when callers/callees are not needed.
    """
    try:
        async with _sessions()() as session:
            return await decompile_mcp_functions(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                functions=functions,
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
    decimal string, or 0x-prefixed hex string), or an exact name (any of
    original/LLM/analyst, case-insensitive). Ambiguous names must be retried
    with id or address.
    Prefers decompiled C; set include_assembly=true only when the C is unclear
    (e.g. inline asm, odd calling conventions, exact constants/offsets).
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
async def get_functions(
    binary_name: str,
    functions: list[McpFunctionSelector],
    binary_version: str = "",
    include_assembly: bool = False,
    include_decompile: bool = True,
) -> McpGetFunctionsDto:
    """Return detailed analysis context for up to 20 functions in one call.

    Each selector sets exactly one of function_id, address, or exact name.
    Unknown, ambiguous, or invalid selectors are reported per entry. The
    include_assembly and include_decompile options apply to every result.
    """
    try:
        async with _sessions()() as session:
            return await get_mcp_functions(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                functions=functions,
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

    Specify exactly one function selector. Only non-null fields are updated.
    name_llm: short descriptive identifier (e.g. decrypt_config_blob).
    summary_short: one line. summary_long: behavior, key inputs/outputs,
    notable APIs/strings. Only record what the code supports; mark guesses.
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


@mcp.tool()
async def search_data(
    binary_name: str,
    binary_version: str = "",
    query: str | None = None,
    kind: str | None = None,
    section: str | None = None,
    min_refs: int | None = None,
    max_refs: int | None = None,
    sort: str = "address",
    limit: int = 50,
    offset: int = 0,
) -> McpDataItemSearchPageDto:
    """Search referenced PE data items in one binary.

    query is a case-insensitive substring of decoded text/import names, address
    (hex or decimal), or a hex byte sequence (for example "de ad be ef").
    kind selects string, bytes, imports, or all
    indexed data kinds (the default). min_refs/max_refs filter by referencing
    instruction count; use max_refs to skip common items.
    sort: address,
    refs_asc (rarest first), refs_desc.
    Use get_data_item to see references.

    Only data locations found through literal addresses in function assembly
    are indexed; imports may be called or merely referenced.
    """
    settings = get_settings()
    try:
        async with _sessions()() as session:
            return await search_mcp_data(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                query=query,
                kind=kind,
                section=section,
                min_refs=min_refs,
                max_refs=max_refs,
                sort=sort,
                limit=limit,
                offset=offset,
                max_limit=settings.function_search_max_limit,
            )
    except AppError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
async def get_data_item(
    binary_name: str,
    binary_version: str = "",
    data_item_id: int | None = None,
    address: int | str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> McpDataItemDetailDto:
    """Return one data item and every function/instruction that references it.

    Specify exactly one of data_item_id or address (integer, decimal string, or
    0x-hex string).
    """
    settings = get_settings()
    try:
        async with _sessions()() as session:
            return await get_mcp_data_item(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                data_item_id=data_item_id,
                address=address,
                limit=limit,
                offset=offset,
                max_limit=settings.function_search_max_limit,
            )
    except AppError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
async def set_data_item_summary(
    binary_name: str,
    binary_version: str = "",
    data_item_id: int | None = None,
    address: int | str | None = None,
    summary_llm: str | None = None,
    clear_summary: bool = False,
) -> McpDataItemUpdateDto:
    """Set or clear the AI summary for one indexed data item.

    Specify exactly one of data_item_id or address. To write a summary, pass
    summary_llm. To remove it, pass clear_summary=true without summary_llm.
    Summaries should state only evidence supported by references and code.
    Re-importing PE data can replace items and erase their summaries.
    """
    try:
        async with write_lock(), _sessions()() as session:
            return await set_mcp_data_item_summary(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                data_item_id=data_item_id,
                address=address,
                summary_llm=summary_llm,
                clear_summary=clear_summary,
            )
    except AppError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
async def get_function_data(
    binary_name: str,
    binary_version: str = "",
    function_id: int | None = None,
    address: int | str | None = None,
    name: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> McpFunctionDataDto:
    """List the data items (strings, imports, globals) one function references.

    Specify exactly one selector: function_id, exact start address, or exact
    name. Quick triage of an unknown function before reading its code.
    """
    settings = get_settings()
    try:
        async with _sessions()() as session:
            return await get_mcp_function_data(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                function_id=function_id,
                address=address,
                name=name,
                limit=limit,
                offset=offset,
                max_limit=settings.function_search_max_limit,
            )
    except AppError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
async def find_functions_by_data(
    binary_name: str,
    binary_version: str = "",
    query: str | None = None,
    kind: str | None = None,
    section: str | None = None,
    min_refs: int | None = None,
    max_refs: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> McpFunctionsByDataPageDto:
    """Find functions using data items matching search_data's filters.

    Each function is returned once with its matching items, e.g. query
    "CreateRemoteThread" or "password". kind accepts string,
    bytes, imports, or all/None. Usually the fastest way to locate relevant code.
    """
    settings = get_settings()
    try:
        async with _sessions()() as session:
            return await find_mcp_functions_by_data(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                query=query,
                kind=kind,
                section=section,
                min_refs=min_refs,
                max_refs=max_refs,
                limit=limit,
                offset=offset,
                max_limit=settings.function_search_max_limit,
            )
    except AppError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
async def find_related_functions(
    binary_name: str,
    binary_version: str = "",
    function_id: int | None = None,
    address: int | str | None = None,
    name: str | None = None,
    max_item_ref_count: int = 20,
    limit: int = 20,
) -> McpRelatedByDataPageDto:
    """Rank other functions by data items shared with the given function.

    Items referenced by more than max_item_ref_count instructions (security
    cookie, common globals) are ignored; rarer shared items weigh more. Each
    result lists the shared items as evidence. Specify exactly one selector.
    Useful for finding sibling functions of the same feature/module that are
    not directly connected in the call graph. Same coverage limits as search_data.
    """
    try:
        async with _sessions()() as session:
            return await find_mcp_related_by_data(
                session,
                binary_name=binary_name,
                binary_version=binary_version,
                function_id=function_id,
                address=address,
                name=name,
                max_item_ref_count=max_item_ref_count,
                limit=limit,
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
