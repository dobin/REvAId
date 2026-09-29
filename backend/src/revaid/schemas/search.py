"""``GET /binaries/{id}/functions`` (search, B11/E1a) and
``GET /binaries/{id}/entry-points`` (E1b) DTOs.

Not given explicit payload shapes in TAD §3.4/§4.3 — these mirror the
`NeighbourPageDto` `rows/total/limit/offset` pattern (§3.4) for consistency
with the rest of the API.
"""

from __future__ import annotations

from pydantic import Field

from revaid.db.models import Function
from revaid_contracts.common import ApiModel


class CodeMatchLineDto(ApiModel):
    line_number: int
    text: str


class FunctionSearchRowDto(ApiModel):
    """A narrow row for the search results list — no code, no long summary,
    matching the `NeighbourRowDto` philosophy of TAD §3.4."""

    id: int
    address: int
    display_name: str
    is_renamed: bool
    kind: str
    is_utility: bool
    fan_in: int
    has_notes: bool
    is_entry_point: bool
    code_matches: list[CodeMatchLineDto] = Field(default_factory=list)
    code_matches_truncated: bool = False


class FunctionSearchPageDto(ApiModel):
    rows: list[FunctionSearchRowDto]
    total: int
    limit: int
    offset: int
    query: str | None


class EntryPointDto(ApiModel):
    id: int
    address: int
    display_name: str
    fan_out: int
    fan_in: int


class EntryPointsDto(ApiModel):
    entry_points: list[EntryPointDto]


def function_search_row_from_function(
    fn: Function,
    *,
    include_code_c: bool = False,
    max_code_matches: int = 20,
    query: str | None = None,
) -> FunctionSearchRowDto:
    code_matches: list[CodeMatchLineDto] = []
    code_matches_truncated = False
    if include_code_c and query and fn.code_c:
        needle = query.casefold()
        for line_number, line in enumerate(fn.code_c.splitlines(), start=1):
            if needle in line.casefold():
                if len(code_matches) == max_code_matches:
                    code_matches_truncated = True
                    break
                code_matches.append(CodeMatchLineDto(line_number=line_number, text=line))
    return FunctionSearchRowDto(
        id=fn.id,
        address=fn.address,
        display_name=fn.name_analyst or fn.name_llm or fn.name,
        is_renamed=fn.name_analyst is not None,
        kind=fn.kind,
        is_utility=fn.is_utility_effective,
        fan_in=fn.fan_in,
        has_notes=fn.notes != "",
        is_entry_point=fn.is_entry_point,
        code_matches=code_matches,
        code_matches_truncated=code_matches_truncated,
    )


def entry_point_dto_from_function(fn: Function) -> EntryPointDto:
    return EntryPointDto(
        id=fn.id,
        address=fn.address,
        display_name=fn.name_analyst or fn.name_llm or fn.name,
        fan_out=fn.fan_out,
        fan_in=fn.fan_in,
    )
