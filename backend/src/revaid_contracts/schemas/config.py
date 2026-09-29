"""``GET /config`` (E1d) and health DTOs — the frontend's only source of F1a thresholds."""

from __future__ import annotations

from pydantic import Field

from revaid_contracts.common import ApiModel

__all__ = [
    "AdapterIdentityDto",
    "AppConfigDto",
    "DecompilerHealthDto",
    "HealthDto",
    "LlmHealthDto",
]


class AdapterIdentityDto(ApiModel):
    ghidra: str
    llm: str
    llm_model: str


class AppConfigDto(ApiModel):
    table_row_cap: int
    caller_suppress_threshold: int
    # `to_camel("utility_fanin_threshold")` would produce `utilityFaninThreshold`;
    # TAD §3.4 specifies `utilityFanInThreshold` (capital I, capital N), so this
    # one field needs an explicit alias override.
    utility_fanin_threshold: int = Field(serialization_alias="utilityFanInThreshold")
    fan_out_all_hard_cap: int
    node_count_soft_warning: int
    card_width_px: int
    summary_concurrency: int
    layout_height_change_threshold_px: int
    layout_animation_ms: int
    # I9 (F1a): fast-scroll debounce guard for row-summary demand acquisition —
    # `hooks/useSummaryDemand.ts` must read this rather than hard-coding 250ms.
    summary_demand_debounce_ms: int
    # ADR 0006 (public mode): an operational flag that rides the same
    # single-payload contract (E1d) so the client only branches on `GET /config`.
    public_mode: bool
    node_color_palette: list[str]
    adapters: AdapterIdentityDto


class LlmHealthDto(ApiModel):
    """AM5: adapter reachability, so the UI can tell "no summaries because
    misconfigured" from "no summaries yet"."""

    reachable: bool
    detail: str | None = None


class DecompilerHealthDto(ApiModel):
    """Reachability of the configured local raw-binary decompiler."""

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
