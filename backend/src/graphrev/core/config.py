"""Application configuration.

This module is the single load-bearing artifact of the whole system's tunability
story (T5, F1, F1a, F1b). Every numeric threshold that the PRD or TAD names must
live here, and nowhere else. ``GET /api/v1/config`` (E1d) is the *only* projection
of this object to the frontend; components must never hard-code a value that
appears below (enforced by ``scripts/check-magic-numbers.sh``).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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

    # Anchored to `backend/.env` (derived from this module's location), NOT
    # cwd-relative: every entrypoint used to require cwd=backend/ for the
    # file to be found, which is how a duplicate root `.env` crept in.
    # A missing file is silently ignored by pydantic-settings.
    model_config = SettingsConfigDict(
        env_prefix="GRAPHREV_",
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- F1: adapters, DB, concurrency -------------------------------------
    db_path: str = Field(default="./graphrev.db", description="Path to the SQLite file (F1).")
    ghidra_adapter: GhidraAdapterName = Field(default="mock")
    llm_adapter: LlmAdapterName = Field(default="mock")
    llm_model: str = Field(default="mock-llm-v1")
    #: I13 (§6.5): LiteLlmAdapter plumbing. `llm_model` is a litellm
    #: router string (e.g. "anthropic/claude-sonnet-4-5", "openai/gpt-4o",
    #: "ollama/llama3") - one adapter covers every provider litellm routes
    #: to (Anthropic/OpenAI/Ollama/vLLM/OpenRouter), which is the point:
    #: V1-V3 retune the model by config alone.
    llm_api_base: str | None = Field(
        default=None,
        description="Base URL for self-hosted/proxied LLM endpoints (litellm api_base).",
    )
    llm_api_key: str | None = Field(
        default=None,
        description="Provider API key (litellm api_key). Prefer the .env file.",
    )
    #: Summarisation is structured extraction, not creative writing: a high
    #: temperature is what makes a model decorate its JSON with markdown
    #: fences or trailing pleasantries (observed live with DeepSeek via
    #: OpenRouter). Default 0 for reproducible, schema-compliant output.
    llm_temperature: float = Field(default=0.0, ge=0, le=2)
    #: Attempts to obtain *parseable* JSON from the model before giving up.
    #: Malformed output is empirically flaky rather than deterministic (the
    #: same function succeeded 25x and failed once), so one retry removes
    #: nearly all spurious SUMMARY_PROVIDER_ERRORs. Only after this many
    #: attempts does the adapter report `PermanentProviderError`.
    llm_json_attempts: int = Field(default=3, gt=0)
    #: Bound on one LiteLLM provider request so a hung provider cannot wedge
    #: a worker slot (§6.5). The worker retains its broader adapter-level
    #: guard for adapters that perform multiple provider attempts.
    summary_request_timeout_seconds: float = Field(default=120.0, gt=0)

    #: I13 (§6.5): OpenCodeAdapter plumbing — `opencode serve` is the sidecar
    #: (plan decision 4: no custom bridge web service, no Node runtime dep in
    #: the backend; just httpx against a port). `opencode_agent` selects the
    #: agent defined in `tools/opencode-ghidra/.opencode/agent/graphrev-re.md`.
    opencode_url: str = Field(default="http://127.0.0.1:4096")
    opencode_agent: str = Field(default="graphrev-re")
    opencode_password: str | None = Field(
        default=None,
        description="OPENCODE_SERVER_PASSWORD of the sidecar (basic auth, user 'opencode').",
    )
    #: §6.3: an unbounded agent on a 1-wide queue is a permanent stall —
    #: bound the agent loop (enforced prompt-side; see tools/opencode-ghidra).
    agent_max_tool_calls: int = Field(default=40, gt=0)
    #: Agent runs are minutes-long, so they get their own bound, wider than
    #: `summary_request_timeout_seconds` (which governs plain LLM calls).
    agent_timeout_seconds: float = Field(default=300.0, gt=0)

    #: C5 "default assumption: 4" — max in-flight LLM generations.
    summary_concurrency: int = Field(default=4, gt=0)
    #: C5 "bounded FIFO queue" — the PRD gives no number; TAD picks 500.
    queue_max_depth: int = Field(default=500, gt=0)

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, gt=0, lt=65536)

    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False, description="JSON logs in prod, console in dev (F2).")

    # -- F1a: the five PRD-named UI tuning constants -----------------------
    table_row_cap: int = Field(default=64, gt=0, description="D6 / F1a / V1.")
    caller_suppress_threshold: int = Field(default=32, gt=0, description="D7 / F1a / V1.")
    utility_fanin_threshold: int = Field(default=50, gt=0, description="D34a / F1a / V2.")
    fan_out_all_hard_cap: int = Field(default=50, gt=0, description="D24 / F1a.")
    node_count_soft_warning: int = Field(default=150, gt=0, description="§5.1 / F1a.")

    # -- TAD-invented additions (docs/adr/0003-invented-constants.md) ------
    card_width_px: int = Field(default=440, gt=0, description="AS23: card width is fixed.")
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
    #: SQLite `PRAGMA synchronous` level. Production default `NORMAL` is the
    #: WAL-safe recommendation. Test suites point at disposable temp DBs and
    #: set `GRAPHREV_SQLITE_SYNCHRONOUS=OFF` to skip fsyncs (durability is
    #: irrelevant for a throwaway file).
    sqlite_synchronous: str = Field(default="NORMAL")

    #: I12 large-export ingestion. Uploads are streamed into this directory
    #: before a process-local worker parses them. The API enforces this cap
    #: while reading, rather than trusting a client supplied Content-Length.
    import_max_upload_bytes: int = Field(default=1024**3, gt=0)
    import_staging_dir: str = Field(default="./.graphrev-imports")
    #: SQLite has one writer; a single import worker prevents competing large
    #: imports from turning its busy timeout into user-visible failures.
    import_worker_concurrency: int = Field(default=1, gt=0, le=1)
    #: Small enough to stay below SQLite's conservative 999 bind-parameter
    #: limit for the function UPSERT's ~14 columns, while replacing thousands
    #: of individual statement/savepoint round trips.
    import_function_batch_size: int = Field(default=50, gt=0, le=50)
    import_edge_batch_size: int = Field(default=200, gt=0, le=200)
    #: Keep completed status records briefly for UI polling. Staged files are
    #: removed as soon as their jobs reach a terminal state.
    import_job_retention_seconds: int = Field(default=3600, gt=0)
    #: Bound API responses and in-memory job state when a malformed export
    #: produces many individual ingestion failures.
    import_failure_sample_limit: int = Field(default=100, gt=0)

    #: Gates `MockLlmAdapter`'s latency/failure simulation (TAD §6.3's
    #: "1-8s latency, ~5% failures" spec). Off by default so `just test` and
    #: everyday `just dev` usage get fast, reliable mock summaries; flip this
    #: on (env `GRAPHREV_MOCK_LLM_SIMULATE_LATENCY=true`) for manual UI
    #: testing of the shimmer/queue-depth/pending-state experience under
    #: realistic timing. NOT exposed on `GET /config` — backend-only knob,
    #: no frontend consumer.
    mock_llm_simulate_latency: bool = Field(
        default=False, description="Enable MockLlmAdapter's simulated latency (see min/max below)."
    )
    mock_llm_min_latency_seconds: float = Field(default=1.0, ge=0)
    mock_llm_max_latency_seconds: float = Field(default=8.0, ge=0)
    #: Kept non-zero even with latency simulation off, so the error+retry UI
    #: state stays reachable in a normal demo. Set to 0 to disable entirely.
    mock_llm_failure_rate: float = Field(default=0.05, ge=0, le=1)

    @model_validator(mode="after")
    def _check_mock_llm_latency_bounds(self) -> Settings:
        if self.mock_llm_min_latency_seconds > self.mock_llm_max_latency_seconds:
            raise ValueError(
                "mock_llm_min_latency_seconds must be <= mock_llm_max_latency_seconds "
                f"(got {self.mock_llm_min_latency_seconds} > {self.mock_llm_max_latency_seconds})"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Process-wide cached Settings instance.

    Cached so every module sees the same values within a process; tests should
    call ``get_settings.cache_clear()`` after mutating environment variables.
    """
    return Settings()
