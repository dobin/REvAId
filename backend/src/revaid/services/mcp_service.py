"""Application services used by the GraphRev MCP server."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from revaid.core.config import get_settings
from revaid.db.enums import DATA_ITEM_KIND_VALUES
from revaid.db.models import Binary, Function
from revaid.repositories.binaries import get_binary_by_name_version, list_binaries
from revaid.repositories.data_items import (
    find_functions_by_matching_items,
    find_related_by_data,
    get_data_item_by_address,
    get_data_item_by_id,
    list_function_refs,
    list_item_refs,
    search_data_items,
)
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
    McpDataItemDetailDto,
    McpDataItemSearchPageDto,
    McpDataRefDto,
    McpDecompiledFunctionDto,
    McpDecompileManyDto,
    McpFunctionDataDto,
    McpFunctionDataRefDto,
    McpFunctionDetailDto,
    McpFunctionQueryResultDto,
    McpFunctionsByDataPageDto,
    McpFunctionSearchPageDto,
    McpFunctionSelector,
    McpFunctionUpdateDto,
    McpFunctionWithDataDto,
    McpGetFunctionsDto,
    McpRelatedByDataDto,
    McpRelatedByDataPageDto,
    mcp_data_item_from_row,
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
    case_insensitive: bool,
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
        case_insensitive=case_insensitive,
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


def _code_hunks(
    code: str, query: str, context: int, *, case_insensitive: bool
) -> tuple[int, list[McpCodeHunkDto]]:
    lines = code.splitlines()
    needle = query.lower() if case_insensitive else query
    hits = [
        i
        for i, text in enumerate(lines)
        if needle in (text.lower() if case_insensitive else text)
    ]
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
    case_insensitive: bool,
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
        session,
        binary_id=binary.id,
        query=query,
        case_insensitive=case_insensitive,
        limit=clamped_limit,
        offset=offset,
    )
    functions: list[McpCodeSearchFunctionDto] = []
    for fn in rows:
        count, hunks = _code_hunks(
            fn.code_c or "", query, context, case_insensitive=case_insensitive
        )
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


async def get_mcp_functions(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    functions: list[McpFunctionSelector],
    include_assembly: bool = False,
    include_decompile: bool = True,
) -> McpGetFunctionsDto:
    """Return detailed analysis context for several functions."""
    binary = await _require_binary(session, binary_name, binary_version)
    if not functions:
        raise AppError(ErrorCode.VALIDATION_ERROR, "functions must not be empty")
    if len(functions) > MAX_DECOMPILE_MANY:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"At most {MAX_DECOMPILE_MANY} functions per call.",
        )

    results: list[McpFunctionQueryResultDto] = []
    for selector in functions:
        try:
            fn = await _resolve_function(
                session,
                binary=binary,
                function_id=selector.function_id,
                address=selector.address,
                name=selector.name,
            )
            callers = await list_callers(session, function_id=fn.id)
            callees = await list_callees(session, function_id=fn.id)
            detail = mcp_function_detail_from_row(
                fn,
                binary_name=binary.name,
                binary_version=binary.version,
                callers=callers,
                callees=callees,
                include_assembly=include_assembly,
                include_decompile=include_decompile,
            )
        except AppError as exc:
            results.append(McpFunctionQueryResultDto(requested=selector, error=exc.message))
            continue
        results.append(McpFunctionQueryResultDto(requested=selector, function=detail))

    return McpGetFunctionsDto(
        binary_name=binary.name,
        binary_version=binary.version,
        functions=results,
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


# -- PE data items -----------------------------------------------------------

_DATA_KINDS = frozenset(DATA_ITEM_KIND_VALUES)
_DATA_SORTS = frozenset({"address", "refs_asc", "refs_desc"})
MAX_RELATED_BY_DATA = 50


def _page_args(limit: int, offset: int, max_limit: int) -> int:
    if limit < 1:
        raise AppError(ErrorCode.VALIDATION_ERROR, "limit must be at least 1")
    if offset < 0:
        raise AppError(ErrorCode.VALIDATION_ERROR, "offset must not be negative")
    return min(limit, max_limit)


def _check_kind(kind: str | None) -> None:
    if kind is not None and kind not in _DATA_KINDS:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"kind must be one of {sorted(_DATA_KINDS)}.",
        )


def _parse_int_address(address: int | str) -> int:
    if isinstance(address, int):
        return address
    text = address.strip()
    try:
        return int(text, 16 if text.lower().startswith("0x") else 10)
    except ValueError as exc:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "address must be an integer, decimal string, or 0x-prefixed hex string.",
        ) from exc


def _display(fn: Function) -> str:
    return fn.name_analyst or fn.name_llm or fn.name


async def search_mcp_data(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    query: str | None,
    kind: str | None,
    section: str | None,
    min_refs: int | None,
    max_refs: int | None,
    sort: str,
    limit: int,
    offset: int,
    max_limit: int,
) -> McpDataItemSearchPageDto:
    binary = await _require_binary(session, binary_name, binary_version)
    clamped = _page_args(limit, offset, max_limit)
    _check_kind(kind)
    if sort not in _DATA_SORTS:
        raise AppError(
            ErrorCode.VALIDATION_ERROR, f"sort must be one of {sorted(_DATA_SORTS)}."
        )
    rows, total = await search_data_items(
        session,
        binary_id=binary.id,
        query=query,
        kind=kind,
        section=section,
        min_refs=min_refs,
        max_refs=max_refs,
        sort=sort,
        limit=clamped,
        offset=offset,
    )
    return McpDataItemSearchPageDto(
        binary_name=binary.name,
        binary_version=binary.version,
        items=[mcp_data_item_from_row(i) for i in rows],
        total=total,
        limit=clamped,
        offset=offset,
        query=query,
    )


async def get_mcp_data_item(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    data_item_id: int | None,
    address: int | str | None,
    limit: int,
    offset: int,
    max_limit: int,
) -> McpDataItemDetailDto:
    binary = await _require_binary(session, binary_name, binary_version)
    if (data_item_id is None) == (address is None):
        raise AppError(
            ErrorCode.VALIDATION_ERROR, "Specify exactly one of data_item_id or address."
        )
    clamped = _page_args(limit, offset, max_limit)
    if data_item_id is not None:
        item = await get_data_item_by_id(session, binary_id=binary.id, data_item_id=data_item_id)
    else:
        assert address is not None
        item = await get_data_item_by_address(
            session, binary_id=binary.id, address=_parse_int_address(address)
        )
    if item is None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "No matching data item; only data referenced from assembly is indexed.",
        )
    refs, total = await list_item_refs(session, data_item_id=item.id, limit=clamped, offset=offset)
    return McpDataItemDetailDto(
        binary_name=binary.name,
        binary_version=binary.version,
        item=mcp_data_item_from_row(item),
        references=[
            McpDataRefDto(
                function_id=r.function.id,
                function_address_hex=f"0x{r.function.address:X}",
                function_display_name=_display(r.function),
                instruction_address_hex=f"0x{r.ref.instruction_address:X}",
                instruction_text=r.ref.instruction_text,
            )
            for r in refs
        ],
        total_references=total,
        limit=clamped,
        offset=offset,
    )


async def get_mcp_function_data(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    function_id: int | None,
    address: int | str | None,
    name: str | None,
    limit: int,
    offset: int,
    max_limit: int,
) -> McpFunctionDataDto:
    binary = await _require_binary(session, binary_name, binary_version)
    fn = await _resolve_function(
        session, binary=binary, function_id=function_id, address=address, name=name
    )
    clamped = _page_args(limit, offset, max_limit)
    refs, total = await list_function_refs(
        session, function_id=fn.id, limit=clamped, offset=offset
    )
    return McpFunctionDataDto(
        binary_name=binary.name,
        binary_version=binary.version,
        function_id=fn.id,
        function_address_hex=f"0x{fn.address:X}",
        function_display_name=_display(fn),
        references=[
            McpFunctionDataRefDto(
                instruction_address_hex=f"0x{r.ref.instruction_address:X}",
                instruction_text=r.ref.instruction_text,
                item=mcp_data_item_from_row(r.item),
            )
            for r in refs
        ],
        total_references=total,
        limit=clamped,
        offset=offset,
    )


async def find_mcp_functions_by_data(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    query: str | None,
    kind: str | None,
    section: str | None,
    min_refs: int | None,
    max_refs: int | None,
    limit: int,
    offset: int,
    max_limit: int,
) -> McpFunctionsByDataPageDto:
    binary = await _require_binary(session, binary_name, binary_version)
    clamped = _page_args(limit, offset, max_limit)
    _check_kind(kind)
    rows, total = await find_functions_by_matching_items(
        session,
        binary_id=binary.id,
        query=query,
        kind=kind,
        section=section,
        min_refs=min_refs,
        max_refs=max_refs,
        limit=clamped,
        offset=offset,
    )
    return McpFunctionsByDataPageDto(
        binary_name=binary.name,
        binary_version=binary.version,
        functions=[
            McpFunctionWithDataDto(
                function=mcp_search_row_from_function(fn),
                matching_items=[mcp_data_item_from_row(i) for i in items],
            )
            for fn, items in rows
        ],
        total=total,
        limit=clamped,
        offset=offset,
        query=query,
    )


async def find_mcp_related_by_data(
    session: AsyncSession,
    *,
    binary_name: str,
    binary_version: str,
    function_id: int | None,
    address: int | str | None,
    name: str | None,
    max_item_ref_count: int,
    limit: int,
) -> McpRelatedByDataPageDto:
    binary = await _require_binary(session, binary_name, binary_version)
    fn = await _resolve_function(
        session, binary=binary, function_id=function_id, address=address, name=name
    )
    if max_item_ref_count < 1:
        raise AppError(ErrorCode.VALIDATION_ERROR, "max_item_ref_count must be at least 1")
    if limit < 1:
        raise AppError(ErrorCode.VALIDATION_ERROR, "limit must be at least 1")
    related = await find_related_by_data(
        session,
        binary_id=binary.id,
        function_id=fn.id,
        max_item_ref_count=max_item_ref_count,
        limit=min(limit, MAX_RELATED_BY_DATA),
    )
    return McpRelatedByDataPageDto(
        binary_name=binary.name,
        binary_version=binary.version,
        function_id=fn.id,
        max_item_ref_count=max_item_ref_count,
        related=[
            McpRelatedByDataDto(
                function=mcp_search_row_from_function(r.function),
                score=round(r.score, 4),
                shared_items=[mcp_data_item_from_row(i) for i in r.shared_items],
            )
            for r in related
        ],
    )
