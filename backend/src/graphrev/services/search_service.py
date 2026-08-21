"""Function search use case (B11, E1a)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.config import Settings
from graphrev.core.errors import AppError, ErrorCode
from graphrev.repositories.binaries import get_binary_by_id
from graphrev.repositories.functions import search_functions
from graphrev.schemas.search import FunctionSearchPageDto, function_search_row_from_function


async def search_functions_dto(
    session: AsyncSession,
    settings: Settings,
    *,
    binary_id: int,
    query: str | None,
    limit: int,
    offset: int,
) -> FunctionSearchPageDto:
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )

    clamped_limit = min(limit, settings.function_search_max_limit)
    functions, total = await search_functions(
        session, binary_id=binary_id, query=query, limit=clamped_limit, offset=offset
    )
    return FunctionSearchPageDto(
        rows=[function_search_row_from_function(fn) for fn in functions],
        total=total,
        limit=clamped_limit,
        offset=offset,
        query=query,
    )
