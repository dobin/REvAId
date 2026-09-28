"""Viewer-facing function DTOs built from analysis API payloads."""

from __future__ import annotations

from pydantic import Field

from revaid_contracts.common import ApiModel


class FunctionSummaryDto(ApiModel):
    status: str
    short: str | None = None
    long: str | None = None
    model: str | None = None
    adapter: str | None = None
    error_code: str | None = None
    low_confidence: bool = False
    generated_at: str | None = None
    is_stale: bool = False


class FunctionDto(ApiModel):
    id: int
    binary_id: int
    address: int
    name: str
    name_analyst: str | None = None
    name_llm: str | None = None
    display_name: str
    is_renamed: bool = False
    kind: str
    placeholder_module: str | None = None
    assembly: str | None = None
    code_c: str | None = None
    parameters: list[dict[str, object]] = Field(default_factory=list)
    signature: str | None = None
    has_indirect_calls: bool = False
    summary_status: str = "none"
    summary_short: str | None = None
    summary: FunctionSummaryDto
    summary_long: str | None = None
    summary_model: str | None = None
    summary_adapter: str | None = None
    summary_error_code: str | None = None
    summary_low_confidence: bool = False
    summary_generated_at: str | None = None
    fan_in: int = 0
    fan_out: int = 0
    is_entry_point: bool = False
    is_utility: bool = False
    is_featured: bool = False
    utility_override: str | None = None
    utility_source: str = "computed"
    notes: str = ""
    notes_updated_at: str | None = None
    has_notes: bool = False
    callee_count: int = 0
    caller_count: int = 0


class FunctionUpdateDto(ApiModel):
    name_analyst: str | None = None
    notes: str | None = None
    is_entry_point: bool | None = None
    is_featured: bool | None = None
    utility_override: str | None = None
