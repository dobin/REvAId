"""Function read + write use cases (E1, D2, D36, E2c).

`name_analyst`/`notes` writes remain I10 scope; I4 adds the `utility_override`
half of `PATCH /functions/{id}`.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.errors import AppError, ErrorCode
from graphrev.repositories.binaries import get_binary_by_id
from graphrev.repositories.functions import (
    get_function_by_id,
    resolve_function_by_address,
    update_utility_override,
)
from graphrev.schemas.function import FunctionDto, FunctionUpdateDto, function_dto_from_row


async def get_function(session: AsyncSession, function_id: int) -> FunctionDto:
    fn = await get_function_by_id(session, function_id)
    if fn is None:
        raise AppError(
            ErrorCode.FUNCTION_NOT_FOUND,
            f"No function {function_id}.",
            details={"functionId": function_id},
        )
    return function_dto_from_row(fn)


async def resolve_by_address(session: AsyncSession, *, binary_id: int, address: int) -> FunctionDto:
    """D2: resolve an address to its containing function within `binary_id`."""
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )
    fn = await resolve_function_by_address(session, binary_id=binary_id, address=address)
    if fn is None:
        raise AppError(
            ErrorCode.ADDRESS_UNRESOLVED,
            f"No function contains address {address:#x} in binary {binary_id}.",
            details={"binaryId": binary_id, "address": address},
        )
    return function_dto_from_row(fn)


async def update_function(
    session: AsyncSession, function_id: int, update: FunctionUpdateDto
) -> FunctionDto:
    """D36/E2c: apply a partial update to a function's analyst-owned fields.

    Only `utility_override` is implemented in I4; fields absent from the
    request body (`model_fields_set`) are left untouched — `None` values that
    *are* explicitly set (e.g. clearing the override) are applied.
    """
    fn = None
    if "utility_override" in update.model_fields_set:
        fn = await update_utility_override(
            session, function_id=function_id, utility_override=update.utility_override
        )
    else:
        fn = await get_function_by_id(session, function_id)

    if fn is None:
        raise AppError(
            ErrorCode.FUNCTION_NOT_FOUND,
            f"No function {function_id}.",
            details={"functionId": function_id},
        )
    await session.commit()
    return function_dto_from_row(fn)
