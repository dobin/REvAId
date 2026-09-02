"""``GET /config`` DTOs (E1d) — the frontend's only source of F1a thresholds."""

from __future__ import annotations

from pydantic import Field

from graphrev.core.config import NODE_COLOR_PALETTE, Settings
from graphrev.schemas.common import ApiModel


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
    # ADR 0006 (public mode): an operational flag, not a threshold, but it
    # rides the same single-payload contract (E1d) so the client never
    # branches on anything but `GET /config`.
    public_mode: bool
    node_color_palette: list[str]
    adapters: AdapterIdentityDto


def app_config_from_settings(settings: Settings) -> AppConfigDto:
    """The single mapping function from ``Settings`` to the wire DTO.

    No component may hard-code a threshold (F1a) and no threshold may be
    duplicated in client code (E1d) — this function is the only place that
    reads ``Settings`` for the purpose of building that payload.
    """
    return AppConfigDto(
        table_row_cap=settings.table_row_cap,
        caller_suppress_threshold=settings.caller_suppress_threshold,
        utility_fanin_threshold=settings.utility_fanin_threshold,
        fan_out_all_hard_cap=settings.fan_out_all_hard_cap,
        node_count_soft_warning=settings.node_count_soft_warning,
        card_width_px=settings.card_width_px,
        summary_concurrency=settings.summary_concurrency,
        layout_height_change_threshold_px=settings.layout_height_change_threshold_px,
        layout_animation_ms=settings.layout_animation_ms,
        summary_demand_debounce_ms=settings.summary_demand_debounce_ms,
        public_mode=settings.public_mode,
        node_color_palette=list(NODE_COLOR_PALETTE),
        adapters=AdapterIdentityDto(
            ghidra=settings.ghidra_adapter,
            llm=settings.llm_adapter,
            llm_model=settings.llm_model,
        ),
    )


class LlmHealthDto(ApiModel):
    """AM5: adapter reachability, so the UI can tell "no summaries because
    misconfigured" from "no summaries yet"."""

    reachable: bool
    detail: str | None = None


class HealthDto(ApiModel):
    status: str
    db_ok: bool
    migration_revision: str | None
    ghidra_adapter: str
    llm_adapter: str
    llm_health: LlmHealthDto
