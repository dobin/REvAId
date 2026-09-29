"""``Settings`` → ``AppConfigDto`` mapping (E1d); the DTOs live in ``revaid_contracts``."""

from __future__ import annotations

from revaid.core.config import Settings
from revaid_contracts.config import NODE_COLOR_PALETTE
from revaid_contracts.schemas.config import AdapterIdentityDto, AppConfigDto


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
