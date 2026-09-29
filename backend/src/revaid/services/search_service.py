"""Function search use case (B11, E1a)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from revaid.core.config import Settings
from revaid.repositories.binaries import get_binary_by_id
from revaid.repositories.functions import search_functions
from revaid.schemas.search import function_search_row_from_function
from revaid_contracts.http_errors import AppError, ErrorCode
from revaid_contracts.schemas.search import FunctionSearchPageDto


async def search_functions_dto(
    session: AsyncSession,
    settings: Settings,
    *,
    binary_id: int,
    query: str | None,
    limit: int,
    offset: int,
    include_code_c: bool = False,
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
        session,
        binary_id=binary_id,
        query=query,
        limit=clamped_limit,
        offset=offset,
        include_code_c=include_code_c,
    )
    return FunctionSearchPageDto(
        rows=[
            function_search_row_from_function(fn, include_code_c=include_code_c, query=query)
            for fn in functions
        ],
        total=total,
        limit=clamped_limit,
        offset=offset,
        query=query,
    )
