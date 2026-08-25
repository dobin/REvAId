"""View use cases — listing + full CRUD (TAD §4.2 #9-#11, I6)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.errors import AppError, ErrorCode
from graphrev.repositories.binaries import get_binary_by_id, update_last_view_id
from graphrev.repositories.functions import get_function_by_id
from graphrev.repositories.views import (
    count_views_by_binary,
    create_view,
    delete_view,
    duplicate_view,
    get_view_by_id,
    list_views_by_binary,
    set_root_function_id,
    update_view_fields,
)
from graphrev.schemas.view import (
    ViewCreateDto,
    ViewDto,
    ViewPatchDto,
    ViewSummaryDto,
    view_dto_from_view,
    view_summary_from_view,
)


async def list_views_dto(session: AsyncSession, binary_id: int) -> list[ViewSummaryDto]:
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )
    views = await list_views_by_binary(session, binary_id=binary_id)
    return [view_summary_from_view(view) for view in views]


async def create_view_dto(session: AsyncSession, binary_id: int, create: ViewCreateDto) -> ViewDto:
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )
    view = await create_view(session, binary_id=binary_id, name=create.name)
    await session.commit()
    created_view = await get_view_by_id(session, view.id)
    assert created_view is not None
    return view_dto_from_view(created_view)


async def get_view_dto(session: AsyncSession, view_id: int) -> ViewDto:
    view = await get_view_by_id(session, view_id)
    if view is None:
        raise AppError(ErrorCode.VIEW_NOT_FOUND, f"No view {view_id}.", details={"viewId": view_id})
    return view_dto_from_view(view)


async def patch_view_dto(session: AsyncSession, view_id: int, patch: ViewPatchDto) -> ViewDto:
    view = await get_view_by_id(session, view_id)
    if view is None:
        raise AppError(ErrorCode.VIEW_NOT_FOUND, f"No view {view_id}.", details={"viewId": view_id})

    fields_set = patch.model_fields_set
    if "root_function_id" in fields_set:
        if patch.root_function_id is not None:
            fn = await get_function_by_id(session, patch.root_function_id)
            if fn is None or fn.binary_id != view.binary_id:
                raise AppError(
                    ErrorCode.FUNCTION_NOT_FOUND,
                    f"No function {patch.root_function_id} in this view's binary.",
                    details={"functionId": patch.root_function_id},
                )
        await set_root_function_id(session, view, patch.root_function_id)

    camera = patch.camera
    await update_view_fields(
        session,
        view,
        name=patch.name,
        camera_x=camera.x if camera else None,
        camera_y=camera.y if camera else None,
        camera_zoom=camera.zoom if camera else None,
    )
    await session.commit()

    view = await get_view_by_id(session, view_id)
    assert view is not None
    return view_dto_from_view(view)


async def delete_view_dto(session: AsyncSession, view_id: int) -> None:
    view = await get_view_by_id(session, view_id)
    if view is None:
        raise AppError(ErrorCode.VIEW_NOT_FOUND, f"No view {view_id}.", details={"viewId": view_id})
    remaining = await count_views_by_binary(session, binary_id=view.binary_id)
    if remaining <= 1:
        raise AppError(
            ErrorCode.LAST_VIEW_DELETE_FORBIDDEN,
            "Cannot delete a binary's only view.",
            details={"viewId": view_id, "binaryId": view.binary_id},
        )
    await delete_view(session, view)
    await session.commit()


async def duplicate_view_dto(session: AsyncSession, view_id: int) -> ViewDto:
    view = await get_view_by_id(session, view_id)
    if view is None:
        raise AppError(ErrorCode.VIEW_NOT_FOUND, f"No view {view_id}.", details={"viewId": view_id})
    new_view = await duplicate_view(session, view)
    await session.commit()
    return view_dto_from_view(new_view)


async def set_last_view(session: AsyncSession, *, binary_id: int, view_id: int) -> None:
    binary = await get_binary_by_id(session, binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )
    view = await get_view_by_id(session, view_id)
    if view is None or view.binary_id != binary_id:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"View {view_id} does not belong to binary {binary_id}.",
            details={"viewId": view_id, "binaryId": binary_id},
        )
    await update_last_view_id(session, binary_id=binary_id, view_id=view_id)
    await session.commit()
