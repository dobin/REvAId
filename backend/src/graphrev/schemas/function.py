"""``GET``/``PATCH /functions/{id}`` DTOs (E1, E2c) — TAD §3.4 ``FunctionDto``."""

from __future__ import annotations

import json

from graphrev.db.enums import UtilityOverride
from graphrev.db.models import Function
from graphrev.schemas.common import ApiModel


class FunctionParamDto(ApiModel):
    ordinal: int
    name: str
    type: str


class FunctionSummaryStateDto(ApiModel):
    status: str
    short: str | None
    long: str | None
    model: str | None
    #: I13/AM4: which adapter produced the summary ("mock"/"litellm"/...).
    #: Exposed for later analysis; no UI affordance yet (decision 6).
    adapter: str | None
    error_code: str | None
    low_confidence: bool
    generated_at: str | None
    is_stale: bool


class FunctionDto(ApiModel):
    id: int
    binary_id: int
    address: int
    display_name: str
    name_ghidra: str
    name_analyst: str | None
    #: C13 auto-display: the LLM-proposed name, when one exists. Display
    #: precedence is `name_analyst ?? name_llm ?? name_ghidra` (server-side,
    #: in `display_name`) — exposed so the UI can show the raw Ghidra name
    #: as a secondary label when the LLM name overrides it.
    name_llm: str | None
    is_renamed: bool
    parameters: list[FunctionParamDto]
    signature: str | None
    assembly: str | None
    code_c: str | None
    kind: str
    placeholder_module: str | None
    fan_in: int
    fan_out: int
    is_utility: bool
    utility_source: str
    utility_override: str | None
    #: I3/E1b: not in the TAD §3.4 sketch — the analyst-owned entry-point
    #: flag added in I3 (see `docs/adr` note in `db/models.py`).
    is_entry_point: bool
    summary: FunctionSummaryStateDto
    notes: str
    has_notes: bool
    notes_updated_at: str | None
    callee_count: int
    caller_count: int
    has_indirect_calls: bool


def function_dto_from_row(fn: Function) -> FunctionDto:
    """The single mapping function from the `Function` ORM row to the wire DTO."""
    parameters = [FunctionParamDto(**p) for p in json.loads(fn.parameters)]
    return FunctionDto(
        id=fn.id,
        binary_id=fn.binary_id,
        address=fn.address,
        display_name=fn.name_analyst or fn.name_llm or fn.name_ghidra,
        name_ghidra=fn.name_ghidra,
        name_analyst=fn.name_analyst,
        name_llm=fn.name_llm,
        is_renamed=fn.name_analyst is not None,
        parameters=parameters,
        signature=fn.signature,
        assembly=fn.assembly,
        code_c=fn.code_c,
        kind=fn.kind,
        placeholder_module=fn.placeholder_module,
        fan_in=fn.fan_in,
        fan_out=fn.fan_out,
        is_utility=fn.is_utility_effective,
        utility_source="analyst" if fn.utility_override is not None else "computed",
        utility_override=fn.utility_override,
        is_entry_point=fn.is_entry_point,
        summary=FunctionSummaryStateDto(
            status=fn.summary_status,
            short=fn.summary_short,
            long=fn.summary_long,
            model=fn.summary_model,
            adapter=fn.summary_adapter,
            error_code=fn.summary_error_code,
            low_confidence=fn.summary_low_confidence,
            generated_at=fn.summary_generated_at,
            is_stale=fn.summary_status == "stale",
        ),
        notes=fn.notes,
        has_notes=fn.notes != "",
        notes_updated_at=fn.notes_updated_at,
        callee_count=fn.fan_out,
        caller_count=fn.fan_in,
        has_indirect_calls=fn.has_indirect_calls,
    )


class FunctionUpdateDto(ApiModel):
    """``PATCH /functions/{id}`` request body (D36/E2c).

    Every field is optional-and-absent-means-"leave unchanged" (Pydantic v2
    ``model_fields_set`` is used by the service layer to distinguish "not
    provided" from "explicitly set to null"). M0 scope is `utility_override`
    only — `name_analyst`/`notes` are I10.
    """

    utility_override: UtilityOverride | None = None
