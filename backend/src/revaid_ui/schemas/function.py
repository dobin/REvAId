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


def function_dto_from_analysis(payload: dict[str, object]) -> FunctionDto:
    """Build the viewer ``FunctionDto`` from an analysis function payload.

    The viewer is a tolerant reader: derived display fields are computed here
    so every route (by id, by address, patch) shares one derivation.
    """
    summary_status = payload.get("summary_status", "none")
    return FunctionDto.model_validate(
        {
            **payload,
            "display_name": (
                payload.get("name_analyst") or payload.get("name_llm") or payload.get("name")
            ),
            "is_renamed": payload.get("name_analyst") is not None,
            "utility_source": (
                "analyst" if payload.get("utility_override") is not None else "computed"
            ),
            "summary": {
                "status": summary_status,
                "short": payload.get("summary_short"),
                "long": payload.get("summary_long"),
                "model": payload.get("summary_model"),
                "adapter": payload.get("summary_adapter"),
                "error_code": payload.get("summary_error_code"),
                "low_confidence": payload.get("summary_low_confidence", False),
                "generated_at": payload.get("summary_generated_at"),
                "is_stale": summary_status == "stale",
            },
            "has_notes": bool(payload.get("notes")),
            "notes_updated_at": payload.get("notes_updated_at"),
            "callee_count": payload.get("fan_out", 0),
            "caller_count": payload.get("fan_in", 0),
        }
    )


class FunctionUpdateDto(ApiModel):
    name_analyst: str | None = None
    notes: str | None = None
    is_entry_point: bool | None = None
    is_featured: bool | None = None
    utility_override: str | None = None
