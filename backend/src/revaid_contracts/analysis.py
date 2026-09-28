"""Typed v1 analysis-service contracts consumed by the optional viewer."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

Direction = Literal["callees", "callers"]
Group = Literal["primary", "utility"]
SortKey = Literal["callOrder", "name", "address", "fanIn"]
SortOrder = Literal["asc", "desc"]
MIN_SUMMARY_PRIORITY = 0
MAX_SUMMARY_PRIORITY = 3

__all__ = [
    "MAX_SUMMARY_PRIORITY",
    "MIN_SUMMARY_PRIORITY",
    "AddressResolution",
    "AddressResolutionRequest",
    "AddressResolutionResponse",
    "AnalysisBinary",
    "AnalysisClient",
    "AnalysisFunction",
    "AnalysisModel",
    "CallPair",
    "CanvasOrigin",
    "CanvasOriginRequest",
    "Direction",
    "FeaturedFunction",
    "FeaturedGraph",
    "FunctionMembership",
    "FunctionMembershipRequest",
    "Group",
    "NeighbourItem",
    "NeighbourPage",
    "NeighbourQuery",
    "ResolvedFunction",
    "SortKey",
    "SortOrder",
]


class AnalysisModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisBinary(AnalysisModel):
    id: int
    name: str
    version: str
    analysis_image_base: int | None
    address_min: int | None = None
    address_max: int | None = None
    function_count: int = 0
    edge_count: int = 0
    created_at: str = ""


class FunctionMembershipRequest(AnalysisModel):
    function_ids: list[int] = Field(max_length=500)


class FunctionMembership(AnalysisModel):
    valid_ids: list[int]


class AddressResolutionRequest(AnalysisModel):
    addresses: list[int] = Field(max_length=500)


class ResolvedFunction(AnalysisModel):
    id: int
    binary_id: int
    address: int
    display_name: str
    kind: str
    placeholder_module: str | None
    assembly: str | None
    code_c: str | None


class AnalysisFunction(ResolvedFunction):
    name: str
    name_analyst: str | None
    name_llm: str | None
    parameters: list[dict[str, object]]
    signature: str | None
    has_indirect_calls: bool
    summary_long: str | None = None
    fan_in: int = 0
    fan_out: int = 0
    is_entry_point: bool = False
    is_utility: bool = False
    is_featured: bool = False
    utility_override: str | None = None
    summary_status: str = "none"
    summary_short: str | None = None
    summary_low_confidence: bool = False
    notes: str = ""
    summary_model: str | None = None
    summary_adapter: str | None = None
    summary_error_code: str | None = None
    summary_generated_at: str | None = None
    notes_updated_at: str | None = None


class AddressResolution(AnalysisModel):
    address: int
    function: ResolvedFunction | None
    containing_function: ResolvedFunction | None = None


class AddressResolutionResponse(AnalysisModel):
    results: list[AddressResolution]


class FeaturedFunction(AnalysisModel):
    id: int


class CallPair(AnalysisModel):
    caller_id: int
    callee_id: int


class FeaturedGraph(AnalysisModel):
    functions: list[FeaturedFunction]
    calls: list[CallPair]


class CanvasOriginRequest(AnalysisModel):
    binary_id: int
    function_id: int
    candidate_ids: list[int] = Field(max_length=499)


class CanvasOrigin(AnalysisModel):
    function_id: int
    origin_function_id: int | None
    origin_kind: Literal["root", "fanout", "fanin"]


class NeighbourQuery(AnalysisModel):
    function_id: int
    direction: Literal["callees", "callers"]
    group: Literal["primary", "utility"]
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)
    sort: Literal["callOrder", "name", "address", "fanIn"]
    order: Literal["asc", "desc"]
    filter_text: str | None = Field(default=None, max_length=256)
    caller_suppress_threshold: int = Field(gt=0)
    table_row_cap: int = Field(gt=0, le=500)


class NeighbourItem(AnalysisModel):
    id: int
    address: int
    display_name: str
    name_llm: str | None
    is_renamed: bool
    summary_short: str | None
    summary_status: str
    summary_low_confidence: bool
    kind: str
    is_utility: bool
    utility_source: str
    fan_in: int
    is_self: bool
    has_notes: bool
    can_fan_out: bool


class NeighbourPage(AnalysisModel):
    function_id: int
    binary_id: int
    anchor_has_indirect_calls: bool
    direction: str
    group: str
    rows: list[NeighbourItem]
    total: int
    total_primary: int
    total_utility: int
    limit: int
    offset: int
    callers_suppressed: bool
    may_be_incomplete: bool


class AnalysisClient(Protocol):
    """Only the analysis reads required by viewer workflows."""

    async def get_binary(self, binary_id: int) -> AnalysisBinary | None: ...

    async def list_binaries(self) -> list[AnalysisBinary]: ...

    async def get_entry_points(self, binary_id: int) -> list[AnalysisFunction]: ...

    async def delete_binary(self, binary_id: int, confirm: str) -> bool: ...

    async def health(self) -> bool: ...

    async def health_details(self) -> dict[str, object]: ...

    async def config(self) -> dict[str, object]: ...

    async def migration_revision(self) -> str | None: ...

    async def get_llm_status(self) -> dict[str, object]: ...

    async def probe_llm(self) -> dict[str, object]: ...

    async def get_queue(self) -> dict[str, object]: ...

    async def cancel_pending(self) -> dict[str, object]: ...

    async def demand_summary(
        self, function_id: int, payload: dict[str, object]
    ) -> dict[str, object]: ...

    async def release_summary(self, function_id: int) -> None: ...

    async def regenerate_summary(self, function_id: int) -> dict[str, object]: ...

    async def clear_binary_summaries(self, binary_id: int) -> None: ...

    async def import_export(self, payload: dict[str, object]) -> dict[str, object]: ...

    async def import_upload(
        self,
        content: AsyncIterator[bytes],
        *,
        content_type: str,
        query: dict[str, str | None] | None = None,
    ) -> dict[str, object]: ...

    async def get_import_status(self, job_id: str) -> dict[str, object]: ...

    async def cancel_import(self, job_id: str) -> dict[str, object]: ...

    async def get_function(self, function_id: int) -> AnalysisFunction | None: ...

    async def validate_function_membership(
        self, binary_id: int, function_ids: list[int]
    ) -> set[int]: ...

    async def resolve_addresses(
        self, binary_id: int, addresses: list[int]
    ) -> dict[int, ResolvedFunction | None]: ...

    async def get_featured_graph(self, binary_id: int) -> FeaturedGraph: ...

    async def find_canvas_origin(
        self, binary_id: int, function_id: int, candidate_ids: set[int]
    ) -> tuple[int, str] | None: ...

    async def get_neighbours(self, query: NeighbourQuery) -> NeighbourPage: ...

    async def search_functions(
        self, binary_id: int, query: str | None, limit: int, offset: int
    ) -> dict[str, object]: ...

    async def resolve_function_by_address(
        self, binary_id: int, address: int
    ) -> dict[str, object]: ...

    async def get_function_detail(self, function_id: int) -> dict[str, object]: ...

    async def update_function(
        self, function_id: int, payload: dict[str, object]
    ) -> dict[str, object]: ...
