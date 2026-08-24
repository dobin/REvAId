"""Application configuration.

This module is the single load-bearing artifact of the whole system's tunability
story (T5, F1, F1a, F1b). Every numeric threshold that the PRD or TAD names must
live here, and nowhere else. ``GET /api/v1/config`` (E1d) is the *only* projection
of this object to the frontend; components must never hard-code a value that
appears below (enforced by ``scripts/check-magic-numbers.sh``).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

GhidraAdapterName = Literal["mock", "rest"]
#: AM3 (docs/specs/PLAN-I7-I8-I9-I13.md): "anthropic" was declared but never
#: implemented; replaced with the two real I13 adapters rather than
#: accumulating a dead variant (closed-enum discipline, docs/adr/0004).
LlmAdapterName = Literal["mock", "litellm", "opencode"]

#: D16 — "a small palette of named tokens, not free-form hex". Only `red` is
#: PRD-hinted (J2); the rest are a TAD invention (docs/adr/0003).
NODE_COLOR_PALETTE: tuple[str, ...] = (
    "slate",
    "red",
    "amber",
    "green",
    "blue",
    "violet",
    "pink",
)


class Settings(BaseSettings):
    """All F1/F1a configuration, loaded from env vars and/or ``.env``.

    Env vars are prefixed ``GRAPHREV_`` (e.g. ``GRAPHREV_TABLE_ROW_CAP=8``).
    """

    model_config = SettingsConfigDict(
        env_prefix="GRAPHREV_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- F1: adapters, DB, concurrency -------------------------------------
    db_path: str = Field(default="./graphrev.db", description="Path to the SQLite file (F1).")
    ghidra_adapter: GhidraAdapterName = Field(default="mock")
    llm_adapter: LlmAdapterName = Field(default="mock")
    llm_model: str = Field(default="mock-llm-v1")

    #: C5 "default assumption: 4" — max in-flight LLM generations.
    summary_concurrency: int = Field(default=4, gt=0)
    #: C5 "bounded FIFO queue" — the PRD gives no number; TAD picks 500.
    queue_max_depth: int = Field(default=500, gt=0)

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, gt=0, lt=65536)

    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False, description="JSON logs in prod, console in dev (F2).")

    # -- F1a: the five PRD-named UI tuning constants -----------------------
    table_row_cap: int = Field(default=16, gt=0, description="D6 / F1a / V1.")
    caller_suppress_threshold: int = Field(default=32, gt=0, description="D7 / F1a / V1.")
    utility_fanin_threshold: int = Field(default=50, gt=0, description="D34a / F1a / V2.")
    fan_out_all_hard_cap: int = Field(default=50, gt=0, description="D24 / F1a.")
    node_count_soft_warning: int = Field(default=150, gt=0, description="§5.1 / F1a.")

    # -- TAD-invented additions (docs/adr/0003-invented-constants.md) ------
    card_width_px: int = Field(default=380, gt=0, description="AS23: card width is fixed.")
    name_analyst_max_length: int = Field(default=128, gt=0, description="§5.1 stated assumption.")

    #: I3 — `GET /binaries/{id}/functions` search pagination (B11/E1a). Not
    #: named anywhere in the PRD/TAD payload examples; these are TAD-style
    #: invented constants, same category as the rest of this section.
    function_search_default_limit: int = Field(default=50, gt=0, description="I3 / B11 / E1a.")
    function_search_max_limit: int = Field(default=200, gt=0, description="I3 / B11 / E1a.")

    #: Debounce intervals (ms). The PRD requires debouncing in five places but
    #: specifies no millisecond value anywhere — these are TAD choices.
    node_patch_debounce_ms: int = Field(default=250, gt=0, description="E3 node PATCH batching.")
    view_patch_debounce_ms: int = Field(
        default=400, gt=0, description="E3a camera/root PATCH, debounced separately."
    )
    notes_autosave_debounce_ms: int = Field(default=600, gt=0, description="D20 notes autosave.")
    summary_demand_debounce_ms: int = Field(
        default=250, gt=0, description="§5.1 fast-scroll guard for row-summary demand."
    )

    #: I6/D11/§4.3 layout re-run trigger + animation duration. Neither value
    #: is PRD/TAD-specified numerically; the TAD's own prose names "8 px"
    #: and "400 ms" (§2.5) but never lifts them into `Settings` — done here
    #: so no component hard-codes either literal (F1a).
    layout_height_change_threshold_px: int = Field(
        default=8,
        gt=0,
        description="D11/§2.5: re-run ELK when a card's measured height changes by more than this.",
    )
    layout_animation_ms: int = Field(
        default=400,
        gt=0,
        description="D11/§2.5: max duration of the position-change CSS transition.",
    )

    #: SSE / SQLite operational tuning (no PRD value given anywhere).
    sse_keepalive_seconds: int = Field(default=15, gt=0)
    sse_subscriber_queue_size: int = Field(default=256, gt=0)
    sqlite_busy_timeout_ms: int = Field(default=5000, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Process-wide cached Settings instance.

    Cached so every module sees the same values within a process; tests should
    call ``get_settings.cache_clear()`` after mutating environment variables.
    """
    return Settings()
