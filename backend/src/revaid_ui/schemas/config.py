"""Viewer-facing health/config DTOs."""

from __future__ import annotations

from pydantic import Field

from revaid_contracts.common import ApiModel


class AdapterIdentityDto(ApiModel):
    ghidra: str
    llm: str
    llm_model: str


class AppConfigDto(ApiModel):
    table_row_cap: int
    caller_suppress_threshold: int
    utility_fanin_threshold: int = Field(serialization_alias="utilityFanInThreshold")
    fan_out_all_hard_cap: int
    node_count_soft_warning: int
    card_width_px: int
    summary_concurrency: int
    layout_height_change_threshold_px: int
    layout_animation_ms: int
    summary_demand_debounce_ms: int
    public_mode: bool
    node_color_palette: list[str]
    adapters: AdapterIdentityDto


class LlmHealthDto(ApiModel):
    reachable: bool
    detail: str | None = None


class DecompilerHealthDto(ApiModel):
    reachable: bool
    detail: str | None = None


class HealthDto(ApiModel):
    status: str
    db_ok: bool
    migration_revision: str | None
    viewer_db_ok: bool
    viewer_migration_revision: str | None
    ghidra_adapter: str
    llm_adapter: str
    llm_health: LlmHealthDto
    decompiler_health: DecompilerHealthDto
