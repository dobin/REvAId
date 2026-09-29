"""Application services used by the GraphRev MCP server."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from revaid.core.config import get_settings
from revaid.db.models import Binary, Function
from revaid.repositories.binaries import get_binary_by_name_version, list_binaries
from revaid.repositories.edges import list_callees, list_callers
from revaid.repositories.functions import (
    get_function_by_address,
    get_function_by_id,
    resolve_functions_by_name,
    search_functions,
    search_functions_by_code,
    update_llm_fields,
)
from revaid.schemas.mcp import (
    McpBinaryDto,
    McpBinaryListDto,
    McpCodeHunkDto,
    McpCodeLineDto,
    McpCodeSearchFunctionDto,
    McpCodeSearchPageDto,
    McpDecompiledFunctionDto,
    McpDecompileManyDto,
    McpFunctionDetailDto,
    McpFunctionSelector,
    McpFunctionSearchPageDto,
    McpFunctionUpdateDto,
    mcp_function_detail_from_row,
    mcp_search_row_from_function,
)
from revaid_contracts.http_errors import AppError, ErrorCode


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


MAX_CONTEXT_LINES = 20
MAX_DECOMPILE_MANY = 20


def _code_hunks(code: str, query: str, context: int) -> tuple[int, list[McpCodeHunkDto]]:
    lines = code.splitlines()
    needle = query.lower()
    hits = [i for i, text in enumerate(lines) if needle in text.lower()]
    hit_set = set(hits)
    ranges: list[list[int]] = []
    for i in hits:
        start, end = max(0, i - context), min(len(lines) - 1, i + context)
        if ranges and start <= ranges[-1][1] + 1:
            ranges[-1][1] = max(ranges[-1][1], end)
        else:
            ranges.append([start, end])
    hunks = [
        McpCodeHunkDto(
            start_line=s + 1,
            end_line=e + 1,
            lines=[
                McpCodeLineDto(line=i + 1, text=lines[i], is_match=i in hit_set)
                for i in range(s, e + 1)
            ],
        )
        for s, e in ranges
    ]
    return len(hits), hunks


async def search_mcp_code(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    query: str,
    context_lines: int,
    limit: int,
    offset: int,
    max_limit: int,
) -> McpCodeSearchPageDto:
    """Grep decompiled C: return matching lines with context per function."""
    binary = await _require_binary(session, binary_name, binary_version)
    if not query:
        raise AppError(ErrorCode.VALIDATION_ERROR, "query must not be empty")
    if limit < 1:
        raise AppError(ErrorCode.VALIDATION_ERROR, "limit must be at least 1")
    if offset < 0:
        raise AppError(ErrorCode.VALIDATION_ERROR, "offset must not be negative")
    context = max(0, min(context_lines, MAX_CONTEXT_LINES))
    clamped_limit = min(limit, max_limit)
    rows, total = await search_functions_by_code(
        session, binary_id=binary.id, query=query, limit=clamped_limit, offset=offset
    )
    functions: list[McpCodeSearchFunctionDto] = []
    for fn in rows:
        count, hunks = _code_hunks(fn.code_c or "", query, context)
        if not hunks:
            continue
        functions.append(
            McpCodeSearchFunctionDto(
                id=fn.id,
                address=fn.address,
                address_hex=f"0x{fn.address:X}",
                display_name=fn.name_analyst or fn.name_llm or fn.name,
                signature=fn.signature,
                match_count=count,
                hunks=hunks,
            )
        )
    return McpCodeSearchPageDto(
        binary_name=binary.name,
        binary_version=binary.version,
        functions=functions,
        total_functions=total,
        limit=clamped_limit,
        offset=offset,
        query=query,
        context_lines=context,
    )


async def decompile_mcp_functions(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    functions: list[McpFunctionSelector],
) -> McpDecompileManyDto:
    """Return decompiled C for several functions; per-item errors do not abort."""
    binary = await _require_binary(session, binary_name, binary_version)
    if not functions:
        raise AppError(ErrorCode.VALIDATION_ERROR, "functions must not be empty")
    if len(functions) > MAX_DECOMPILE_MANY:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"At most {MAX_DECOMPILE_MANY} functions per call.",
        )
    results: list[McpDecompiledFunctionDto] = []
    for sel in functions:
        try:
            fn = await _resolve_function(
                session,
                binary=binary,
                function_id=sel.function_id,
                address=sel.address,
                name=sel.name,
            )
        except AppError as exc:
            results.append(McpDecompiledFunctionDto(requested=sel, error=exc.message))
            continue
        results.append(
            McpDecompiledFunctionDto(
                requested=sel,
                id=fn.id,
                address=fn.address,
                address_hex=f"0x{fn.address:X}",
                display_name=fn.name_analyst or fn.name_llm or fn.name,
                signature=fn.signature,
                code_c=fn.code_c,
            )
        )
    return McpDecompileManyDto(
        binary_name=binary.name, binary_version=binary.version, functions=results
    )


async def get_mcp_function(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    function_id: int | None = None,
    address: int | str | None = None,
    name: str | None = None,
    include_assembly: bool = False,
    include_decompile: bool = True,
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
        include_assembly=include_assembly,
        include_decompile=include_decompile,
    )


async def set_mcp_function_info(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    function_id: int | None = None,
    address: int | str | None = None,
    name: str | None = None,
    name_llm: str | None = None,
    summary_short: str | None = None,
    summary_long: str | None = None,
) -> McpFunctionUpdateDto:
    """Set the supplied non-null LLM-authored fields."""
    if get_settings().public_mode:
        raise AppError(
            ErrorCode.PUBLIC_MODE_FORBIDDEN,
            "Function updates are disabled (public mode).",
        )

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
        display_name=updated.name_analyst or updated.name_llm or updated.name,
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
    address: int | str | None,
    name: str | None,
) -> Function:
    selectors = sum(value is not None for value in (function_id, address, name))
    if selectors != 1:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "Specify exactly one of function_id, address, or name.",
        )

    parsed_address: int | None = None
    if isinstance(address, int):
        parsed_address = address
    elif address is not None:
        address_text = address.strip()
        try:
            parsed_address = int(
                address_text,
                16 if address_text.lower().startswith("0x") else 10,
            )
        except ValueError as exc:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "address must be an integer, decimal string, or 0x-prefixed hex string.",
            ) from exc

    fn: Function | None
    if function_id is not None:
        fn = await get_function_by_id(session, function_id)
        if fn is not None and fn.binary_id != binary.id:
            fn = None
    elif parsed_address is not None:
        fn = await get_function_by_address(session, binary_id=binary.id, address=parsed_address)
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
