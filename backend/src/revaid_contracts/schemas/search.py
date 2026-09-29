"""Function search (B11/E1a) and entry-point (E1b) DTOs."""

from __future__ import annotations

from revaid_contracts.common import ApiModel

__all__ = [
    "CodeMatchLineDto",
    "EntryPointDto",
    "EntryPointsDto",
    "FunctionSearchPageDto",
    "FunctionSearchRowDto",
]


class CodeMatchLineDto(ApiModel):
    line_number: int
    text: str


class FunctionSearchRowDto(ApiModel):
    """A narrow row for the search results list — no code, no long summary."""

    id: int
    address: int
    display_name: str
    is_renamed: bool
    kind: str
    is_utility: bool
    fan_in: int
    has_notes: bool
    is_entry_point: bool
    code_matches: list[CodeMatchLineDto]
    code_matches_truncated: bool


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
