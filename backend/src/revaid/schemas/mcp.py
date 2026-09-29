"""Structured outputs for the GraphRev MCP tools."""

from __future__ import annotations

from revaid.db.models import DataItem, Function
from revaid.repositories.edges import RelatedFunction
from revaid.schemas.function import (
    FunctionParamDto,
    FunctionSummaryStateDto,
    function_dto_from_row,
)
from revaid_contracts.common import ApiModel


class McpBinaryDto(ApiModel):
    name: str
    version: str
    function_count: int
    edge_count: int


class McpBinaryListDto(ApiModel):
    binaries: list[McpBinaryDto]


class McpFunctionSearchRowDto(ApiModel):
    id: int
    address: int
    address_hex: str
    display_name: str
    name: str
    name_llm: str | None
    name_analyst: str | None
    kind: str
    signature: str | None
    summary_short: str | None
    fan_in: int
    fan_out: int


class McpFunctionSearchPageDto(ApiModel):
    binary_name: str
    binary_version: str
    functions: list[McpFunctionSearchRowDto]
    total: int
    limit: int
    offset: int
    query: str | None


class McpRelatedFunctionDto(ApiModel):
    id: int
    address: int
    address_hex: str
    display_name: str
    name: str
    name_llm: str | None
    kind: str
    signature: str | None
    summary_short: str | None
    callee_order: int | None
    edge_kind: str


class McpFunctionDetailDto(ApiModel):
    id: int
    binary_name: str
    binary_version: str
    address: int
    address_hex: str
    display_name: str
    name: str
    name_llm: str | None
    name_analyst: str | None
    parameters: list[FunctionParamDto]
    signature: str | None
    assembly: str | None
    code_c: str | None
    kind: str
    placeholder_module: str | None
    has_indirect_calls: bool
    fan_in: int
    fan_out: int
    is_entry_point: bool
    summary: FunctionSummaryStateDto
    callers: list[McpRelatedFunctionDto]
    callees: list[McpRelatedFunctionDto]


class McpCodeLineDto(ApiModel):
    line: int
    text: str
    is_match: bool


class McpCodeHunkDto(ApiModel):
    start_line: int
    end_line: int
    lines: list[McpCodeLineDto]


class McpCodeSearchFunctionDto(ApiModel):
    id: int
    address: int
    address_hex: str
    display_name: str
    signature: str | None
    match_count: int
    hunks: list[McpCodeHunkDto]


class McpCodeSearchPageDto(ApiModel):
    binary_name: str
    binary_version: str
    functions: list[McpCodeSearchFunctionDto]
    total_functions: int
    limit: int
    offset: int
    query: str
    context_lines: int


class McpFunctionSelector(ApiModel):
    function_id: int | None = None
    address: int | str | None = None
    name: str | None = None


class McpDecompiledFunctionDto(ApiModel):
    requested: McpFunctionSelector
    id: int | None = None
    address: int | None = None
    address_hex: str | None = None
    display_name: str | None = None
    signature: str | None = None
    code_c: str | None = None
    error: str | None = None


class McpDecompileManyDto(ApiModel):
    binary_name: str
    binary_version: str
    functions: list[McpDecompiledFunctionDto]


class McpFunctionUpdateDto(ApiModel):
    id: int
    binary_name: str
    binary_version: str
    address: int
    address_hex: str
    display_name: str
    name_llm: str | None
    summary_short: str | None
    summary_long: str | None
    summary_status: str
    updated_fields: list[str]


def mcp_search_row_from_function(fn: Function) -> McpFunctionSearchRowDto:
    return McpFunctionSearchRowDto(
        id=fn.id,
        address=fn.address,
        address_hex=f"0x{fn.address:X}",
        display_name=fn.name_analyst or fn.name_llm or fn.name,
        name=fn.name,
        name_llm=fn.name_llm,
        name_analyst=fn.name_analyst,
        kind=fn.kind,
        signature=fn.signature,
        summary_short=fn.summary_short,
        fan_in=fn.fan_in,
        fan_out=fn.fan_out,
    )


def mcp_related_function_from_row(row: RelatedFunction) -> McpRelatedFunctionDto:
    fn = row.function
    return McpRelatedFunctionDto(
        id=fn.id,
        address=fn.address,
        address_hex=f"0x{fn.address:X}",
        display_name=fn.name_analyst or fn.name_llm or fn.name,
        name=fn.name,
        name_llm=fn.name_llm,
        kind=fn.kind,
        signature=fn.signature,
        summary_short=fn.summary_short,
        callee_order=row.callee_order,
        edge_kind=row.kind,
    )


def mcp_function_detail_from_row(
    fn: Function,
    *,
    binary_name: str,
    binary_version: str,
    callers: list[RelatedFunction],
    callees: list[RelatedFunction],
    include_assembly: bool = False,
    include_decompile: bool = True,
) -> McpFunctionDetailDto:
    base = function_dto_from_row(fn)
    return McpFunctionDetailDto(
        id=base.id,
        binary_name=binary_name,
        binary_version=binary_version,
        address=base.address,
        address_hex=f"0x{base.address:X}",
        display_name=base.display_name,
        name=base.name,
        name_llm=base.name_llm,
        name_analyst=base.name_analyst,
        parameters=base.parameters,
        signature=base.signature,
        assembly=base.assembly if include_assembly else None,
        code_c=base.code_c if include_decompile else None,
        kind=base.kind,
        placeholder_module=base.placeholder_module,
        has_indirect_calls=base.has_indirect_calls,
        fan_in=base.fan_in,
        fan_out=base.fan_out,
        is_entry_point=base.is_entry_point,
        summary=base.summary,
        callers=[mcp_related_function_from_row(row) for row in callers],
        callees=[mcp_related_function_from_row(row) for row in callees],
    )


# -- PE data items (raw-binary imports; references parsed from assembly) ----


class McpDataItemDto(ApiModel):
    id: int
    address: int
    address_hex: str
    rva_hex: str
    section: str
    kind: str
    size: int
    value_text: str | None
    target_address_hex: str | None
    preview_hex: str | None
    is_writable: bool
    ref_count: int


class McpDataItemSearchPageDto(ApiModel):
    binary_name: str
    binary_version: str
    items: list[McpDataItemDto]
    total: int
    limit: int
    offset: int
    query: str | None


class McpDataRefDto(ApiModel):
    """One instruction referencing a data item (parsed from assembly text)."""

    function_id: int
    function_address_hex: str
    function_display_name: str
    instruction_address_hex: str
    instruction_text: str


class McpDataItemDetailDto(ApiModel):
    binary_name: str
    binary_version: str
    item: McpDataItemDto
    references: list[McpDataRefDto]
    total_references: int
    limit: int
    offset: int


class McpFunctionDataRefDto(ApiModel):
    instruction_address_hex: str
    instruction_text: str
    item: McpDataItemDto


class McpFunctionDataDto(ApiModel):
    binary_name: str
    binary_version: str
    function_id: int
    function_address_hex: str
    function_display_name: str
    references: list[McpFunctionDataRefDto]
    total_references: int
    limit: int
    offset: int


class McpFunctionWithDataDto(ApiModel):
    function: McpFunctionSearchRowDto
    matching_items: list[McpDataItemDto]


class McpFunctionsByDataPageDto(ApiModel):
    binary_name: str
    binary_version: str
    functions: list[McpFunctionWithDataDto]
    total: int
    limit: int
    offset: int
    query: str | None


class McpRelatedByDataDto(ApiModel):
    function: McpFunctionSearchRowDto
    score: float
    shared_items: list[McpDataItemDto]


class McpRelatedByDataPageDto(ApiModel):
    binary_name: str
    binary_version: str
    function_id: int
    max_item_ref_count: int
    related: list[McpRelatedByDataDto]


def mcp_data_item_from_row(item: DataItem) -> McpDataItemDto:
    return McpDataItemDto(
        id=item.id,
        address=item.address,
        address_hex=f"0x{item.address:X}",
        rva_hex=f"0x{item.rva:X}",
        section=item.section,
        kind=item.kind,
        size=item.size,
        value_text=item.value_text,
        target_address_hex=(
            f"0x{item.target_address:X}" if item.target_address is not None else None
        ),
        preview_hex=item.preview_hex,
        is_writable=item.is_writable,
        ref_count=item.ref_count,
    )
