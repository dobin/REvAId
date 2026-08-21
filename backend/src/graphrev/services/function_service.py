"""Function read use cases (E1, D2).

Write operations (rename, notes, utility_override, is_entry_point toggle —
`PATCH /functions/{id}`) are I4 scope; this module is deliberately read-only.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.errors import AppError, ErrorCode
from graphrev.repositories.binaries import get_binary_by_id
from graphrev.repositories.functions import get_function_by_id, resolve_function_by_address
from graphrev.schemas.function import FunctionDto, function_dto_from_row


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
