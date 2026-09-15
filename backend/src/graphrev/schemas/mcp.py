"""Structured outputs for the GraphRev MCP tools."""

from __future__ import annotations

from graphrev.db.models import Function
from graphrev.repositories.edges import RelatedFunction
from graphrev.schemas.common import ApiModel
from graphrev.schemas.function import (
    FunctionParamDto,
    FunctionSummaryStateDto,
    function_dto_from_row,
)


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
    name_ghidra: str
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
    name_ghidra: str
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
    name_ghidra: str
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
        display_name=fn.name_analyst or fn.name_llm or fn.name_ghidra,
        name_ghidra=fn.name_ghidra,
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
        display_name=fn.name_analyst or fn.name_llm or fn.name_ghidra,
        name_ghidra=fn.name_ghidra,
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
) -> McpFunctionDetailDto:
    base = function_dto_from_row(fn)
    return McpFunctionDetailDto(
        id=base.id,
        binary_name=binary_name,
        binary_version=binary_version,
        address=base.address,
        address_hex=f"0x{base.address:X}",
        display_name=base.display_name,
        name_ghidra=base.name_ghidra,
        name_llm=base.name_llm,
        name_analyst=base.name_analyst,
        parameters=base.parameters,
        signature=base.signature,
        assembly=base.assembly,
        code_c=base.code_c,
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
