"""Shared Pydantic base — the camelCase wire contract (TAD §4).

Every DTO in ``schemas/`` inherits :class:`ApiModel` so the wire format is
consistently ``camelCase`` while Python code stays ``snake_case``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
