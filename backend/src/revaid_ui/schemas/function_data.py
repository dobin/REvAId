"""``GET /functions/{id}/data`` DTOs: PE data a function accesses."""

from __future__ import annotations

from typing import Any

from revaid_contracts.common import ApiModel


class DataItemDto(ApiModel):
    id: int
    address: int
    section: str | None
    kind: str
    size: int
    value_text: str | None
    preview_hex: str | None = None
    is_writable: bool
    ref_count: int


class FunctionDataRefDto(ApiModel):
    instruction_address: int
    instruction_text: str
    item: DataItemDto


class FunctionDataDto(ApiModel):
    function_id: int
    references: list[FunctionDataRefDto]
    total: int
    limit: int
    offset: int


def function_data_dto_from_analysis(payload: dict[str, Any]) -> FunctionDataDto:
    return FunctionDataDto(
        function_id=payload["function_id"],
        references=[
            FunctionDataRefDto(
                instruction_address=ref["instruction_address"],
                instruction_text=ref["instruction_text"],
                item=DataItemDto(**ref["item"]),
            )
            for ref in payload["references"]
        ],
        total=payload["total"],
        limit=payload["limit"],
        offset=payload["offset"],
    )
