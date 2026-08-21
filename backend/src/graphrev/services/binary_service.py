"""Binary use cases (E1): list, typed-confirm delete, entry-point suggestions."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.errors import AppError, ErrorCode
from graphrev.repositories.binaries import delete_binary, get_binary_by_id, list_binaries
from graphrev.repositories.functions import list_entry_points
from graphrev.schemas.binary import BinarySummaryDto, binary_summary_from_row
from graphrev.schemas.search import EntryPointDto, EntryPointsDto, entry_point_dto_from_function

#: E1b: "≤ 5 empty-canvas suggestions" — enforced server-side regardless of
#: whatever a caller might request, since there is no query parameter for it
#: in the TAD endpoint index.
_MAX_ENTRY_POINTS = 5


async def list_binaries_dto(session: AsyncSession) -> list[BinarySummaryDto]:
    rows = await list_binaries(session)
    return [binary_summary_from_row(row) for row in rows]


async def delete_binary_with_confirmation(
    session: AsyncSession, *, binary_id: int, confirm: str
) -> None:
    """Typed-confirm destructive delete (E1).

    Raises `BINARY_NOT_FOUND` if `binary_id` does not exist, or
    `CONFIRMATION_MISMATCH` if `confirm` does not exactly match the binary's
    `name`. Cascade to functions/edges/views/view_nodes is handled entirely
    by the DB-level `ON DELETE CASCADE` foreign keys (see `db/models.py`).
    """
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )
    if confirm != binary.name:
        raise AppError(
            ErrorCode.CONFIRMATION_MISMATCH,
            "Confirmation text does not match the binary name.",
            details={"binaryId": binary_id, "expected": binary.name},
        )
    await delete_binary(session, binary)
    await session.commit()


async def get_entry_points(session: AsyncSession, binary_id: int) -> EntryPointsDto:
    """E1b: up to 5 entry-point suggestions for an empty canvas."""
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )
    functions = await list_entry_points(session, binary_id=binary_id, limit=_MAX_ENTRY_POINTS)
    entry_points: list[EntryPointDto] = [entry_point_dto_from_function(fn) for fn in functions]
    return EntryPointsDto(entry_points=entry_points)
