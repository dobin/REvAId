"""Application services used by the GraphRev MCP server."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.errors import AppError, ErrorCode
from graphrev.db.models import Binary, Function
from graphrev.repositories.binaries import get_binary_by_name_version, list_binaries
from graphrev.repositories.edges import list_callees, list_callers
from graphrev.repositories.functions import (
    get_function_by_address,
    get_function_by_id,
    resolve_functions_by_name,
    search_functions,
    update_llm_fields,
)
from graphrev.schemas.mcp import (
    McpBinaryDto,
    McpBinaryListDto,
    McpFunctionDetailDto,
    McpFunctionSearchPageDto,
    McpFunctionUpdateDto,
    mcp_function_detail_from_row,
    mcp_search_row_from_function,
)


async def list_mcp_binaries(session: AsyncSession) -> McpBinaryListDto:
    rows = await list_binaries(session)
    return McpBinaryListDto(
        binaries=[
            McpBinaryDto(
                name=row.binary.name,
                version=row.binary.version,
                function_count=row.function_count,
                edge_count=row.edge_count,
            )
            for row in rows
        ]
    )


async def find_mcp_functions(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    query: str | None,
    limit: int,
    offset: int,
    max_limit: int,
) -> McpFunctionSearchPageDto:
    binary = await _require_binary(session, binary_name, binary_version)
    if limit < 1:
        raise AppError(ErrorCode.VALIDATION_ERROR, "limit must be at least 1")
    if offset < 0:
        raise AppError(ErrorCode.VALIDATION_ERROR, "offset must not be negative")
    clamped_limit = min(limit, max_limit)
    rows, total = await search_functions(
        session,
        binary_id=binary.id,
        query=query,
        limit=clamped_limit,
        offset=offset,
        include_code_c=True,
    )
    return McpFunctionSearchPageDto(
        binary_name=binary.name,
        binary_version=binary.version,
        functions=[mcp_search_row_from_function(fn) for fn in rows],
        total=total,
        limit=clamped_limit,
        offset=offset,
        query=query,
    )


async def get_mcp_function(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    function_id: int | None = None,
    address: int | None = None,
    name: str | None = None,
) -> McpFunctionDetailDto:
    binary = await _require_binary(session, binary_name, binary_version)
    fn = await _resolve_function(
        session,
        binary=binary,
        function_id=function_id,
        address=address,
        name=name,
    )
    callers = await list_callers(session, function_id=fn.id)
    callees = await list_callees(session, function_id=fn.id)
    return mcp_function_detail_from_row(
        fn,
        binary_name=binary.name,
        binary_version=binary.version,
        callers=callers,
        callees=callees,
    )


async def set_mcp_function_info(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    function_id: int | None = None,
    address: int | None = None,
    name: str | None = None,
    name_llm: str | None = None,
    summary_short: str | None = None,
    summary_long: str | None = None,
) -> McpFunctionUpdateDto:
    """Set the supplied non-null LLM-authored fields."""
    binary = await _require_binary(session, binary_name, binary_version)
    fn = await _resolve_function(
        session,
        binary=binary,
        function_id=function_id,
        address=address,
        name=name,
    )
    values: dict[str, str | None] = {}
    if name_llm is not None:
        values["name_llm"] = name_llm
    if summary_short is not None:
        values["summary_short"] = summary_short
    if summary_long is not None:
        values["summary_long"] = summary_long
    if not values:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Supply at least one of name_llm, summary_short, or summary_long.",
        )

    updated = await update_llm_fields(session, function_id=fn.id, values=values)
    if updated is None:
        raise AppError(ErrorCode.FUNCTION_NOT_FOUND, f"No function {fn.id}.")
    await session.commit()
    return McpFunctionUpdateDto(
        id=updated.id,
        binary_name=binary.name,
        binary_version=binary.version,
        address=updated.address,
        address_hex=f"0x{updated.address:X}",
        display_name=updated.name_analyst or updated.name_llm or updated.name_ghidra,
        name_llm=updated.name_llm,
        summary_short=updated.summary_short,
        summary_long=updated.summary_long,
        summary_status=updated.summary_status,
        updated_fields=sorted(values),
    )


async def _require_binary(session: AsyncSession, binary_name: str, binary_version: str) -> Binary:
    binary = await get_binary_by_name_version(session, name=binary_name, version=binary_version)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_name!r} with version {binary_version!r}.",
            details={"binaryName": binary_name, "binaryVersion": binary_version},
        )
    return binary


async def _resolve_function(
    session: AsyncSession,
    *,
    binary: Binary,
    function_id: int | None,
    address: int | None,
    name: str | None,
) -> Function:
    selectors = sum(value is not None for value in (function_id, address, name))
    if selectors != 1:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Specify exactly one of function_id, address, or name.",
        )

    fn: Function | None
    if function_id is not None:
        fn = await get_function_by_id(session, function_id)
        if fn is not None and fn.binary_id != binary.id:
            fn = None
    elif address is not None:
        fn = await get_function_by_address(session, binary_id=binary.id, address=address)
    else:
        matches = await resolve_functions_by_name(session, binary_id=binary.id, name=name or "")
        if len(matches) > 1:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                f"Function name {name!r} is ambiguous; use function_id or address.",
                details={
                    "matches": [{"id": match.id, "address": match.address} for match in matches]
                },
            )
        fn = matches[0] if matches else None

    if fn is None:
        raise AppError(
            ErrorCode.FUNCTION_NOT_FOUND,
            f"No matching function in binary {binary.name!r} version {binary.version!r}.",
        )
    return fn
