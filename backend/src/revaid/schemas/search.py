"""``Function`` row → search/entry-point DTO mappings; DTOs live in ``revaid_contracts``."""

from __future__ import annotations

from revaid.db.models import Function
from revaid_contracts.schemas.search import (
    CodeMatchLineDto,
    EntryPointDto,
    FunctionSearchRowDto,
)


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
