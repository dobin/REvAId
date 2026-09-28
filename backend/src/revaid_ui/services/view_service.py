"""Viewer view use cases with analysis facts supplied through AnalysisClient."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revaid_contracts.analysis import AnalysisClient, CallPair, FeaturedFunction
from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_ui.core.ids import random_view_id
from revaid_ui.db.models import View
from revaid_ui.repositories.views import (
    clear_last_view_ids_for_view,
    count_views_by_binary,
    create_view,
    delete_view,
    duplicate_view,
    get_view_by_id,
    list_views_by_binary,
    set_last_view_id,
    set_root_function_id,
    update_view_fields,
)
from revaid_ui.schemas.view import (
    ViewCreateDto,
    ViewDto,
    ViewPatchDto,
    ViewSummaryDto,
    view_dto_from_view,
    view_summary_from_view,
)
from revaid_ui.viewer.seed import create_default_view, seed_view_from_analysis


async def list_views_dto(
    session: AsyncSession, analysis: AnalysisClient, binary_id: int
) -> list[ViewSummaryDto]:
    binary = await analysis.get_binary(binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )
    views = await list_views_by_binary(session, binary_id=binary_id)
    if not views:
        # View state is optional and owned by the viewer API. Create its
        # initial canvas lazily when a client first opens the binary instead
        # of coupling core ingestion to the UI database/domain.
        graph = await analysis.get_featured_graph(binary_id)
        valid_ids = await analysis.validate_function_membership(
            binary_id, [function.id for function in graph.functions]
        )
        functions = [function for function in graph.functions if function.id in valid_ids]
        featured_ids = {function.id for function in functions}
        calls = [
            call
            for call in graph.calls
            if call.caller_id in featured_ids and call.callee_id in featured_ids
        ]
        view = await create_default_view(session, binary_id)
        _seed_view_from_analysis(session, view, functions, calls)
        await session.commit()
        views = await list_views_by_binary(session, binary_id=binary_id)
    return [view_summary_from_view(view) for view in views]


def _seed_view_from_analysis(
    session: AsyncSession,
    view: View,
    featured_functions: list[FeaturedFunction],
    calls: list[CallPair],
) -> None:
    seed_view_from_analysis(
        session,
        view,
        featured_ids=[function.id for function in featured_functions],
        call_pairs=[(call.caller_id, call.callee_id) for call in calls],
    )


async def create_view_dto(
    session: AsyncSession,
    analysis: AnalysisClient,
    binary_id: int,
    create: ViewCreateDto,
    *,
    random_id: bool = False,
) -> ViewDto:
    binary = await analysis.get_binary(binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )
    graph = await analysis.get_featured_graph(binary_id)
    valid_ids = await analysis.validate_function_membership(
        binary_id, [function.id for function in graph.functions]
    )
    functions = [function for function in graph.functions if function.id in valid_ids]
    featured_ids = {function.id for function in functions}
    calls = [
        call
        for call in graph.calls
        if call.caller_id in featured_ids and call.callee_id in featured_ids
    ]
    view = await _create_view_with_optional_random_id(
        session, binary_id=binary_id, name=create.name, random_id=random_id
    )
    _seed_view_from_analysis(session, view, functions, calls)
    await session.commit()
    created_view = await get_view_by_id(session, view.id)
    assert created_view is not None
    return view_dto_from_view(created_view)


async def _create_view_with_optional_random_id(
    session: AsyncSession, *, binary_id: int, name: str, random_id: bool
) -> View:
    """Create a view, generating a random id when `random_id` is set (ADR
    0006: in public mode a view id is an unguessable capability). A random
    id can collide with an existing row, so retry a bounded number of times
    — the range is 2^53, so a collision is vanishingly rare and the retry
    loop is a correctness backstop, not a hot path."""
    if not random_id:
        return await create_view(session, binary_id=binary_id, name=name)

    for _attempt in range(3):
        try:
            return await create_view(
                session, binary_id=binary_id, name=name, view_id=random_view_id()
            )
        except IntegrityError:
            # Flush raised on a duplicate random id — roll the insert back and
            # try again. The session is still usable for a retry only if the
            # failed flush didn't poison the transaction; a fresh nested
            # transaction keeps the outer write session clean.
            await session.rollback()
    raise AppError(
        ErrorCode.INTERNAL_ERROR,
        "Could not allocate a unique view id.",
        details={"binaryId": binary_id},
    )


async def get_view_dto(session: AsyncSession, view_id: int) -> ViewDto:
    view = await get_view_by_id(session, view_id)
    if view is None:
        raise AppError(ErrorCode.VIEW_NOT_FOUND, f"No view {view_id}.", details={"viewId": view_id})
    return view_dto_from_view(view)


async def patch_view_dto(
    session: AsyncSession,
    analysis: AnalysisClient,
    view_id: int,
    patch: ViewPatchDto,
) -> ViewDto:
    view = await get_view_by_id(session, view_id)
    if view is None:
        raise AppError(ErrorCode.VIEW_NOT_FOUND, f"No view {view_id}.", details={"viewId": view_id})

    fields_set = patch.model_fields_set
    if "root_function_id" in fields_set:
        if patch.root_function_id is not None:
            valid_ids = await analysis.validate_function_membership(
                view.binary_id, [patch.root_function_id]
            )
            if patch.root_function_id not in valid_ids:
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
    await clear_last_view_ids_for_view(session, view_id=view_id)
    await session.commit()


async def duplicate_view_dto(
    session: AsyncSession, view_id: int, *, random_id: bool = False
) -> ViewDto:
    view = await get_view_by_id(session, view_id)
    if view is None:
        raise AppError(ErrorCode.VIEW_NOT_FOUND, f"No view {view_id}.", details={"viewId": view_id})
    new_view = await _duplicate_view_with_optional_random_id(session, view, random_id=random_id)
    await session.commit()
    return view_dto_from_view(new_view)


async def _duplicate_view_with_optional_random_id(
    session: AsyncSession, view: View, *, random_id: bool
) -> View:
    if not random_id:
        return await duplicate_view(session, view)

    for _attempt in range(3):
        try:
            return await duplicate_view(session, view, view_id=random_view_id())
        except IntegrityError:
            await session.rollback()
    raise AppError(
        ErrorCode.INTERNAL_ERROR,
        "Could not allocate a unique view id.",
        details={"viewId": view.id},
    )


async def set_last_view(
    analysis: AnalysisClient,
    viewer_session: AsyncSession,
    *,
    binary_id: int,
    view_id: int,
) -> None:
    binary = await analysis.get_binary(binary_id)
    if binary is None:
        raise AppError(
            ErrorCode.BINARY_NOT_FOUND,
            f"No binary {binary_id}.",
            details={"binaryId": binary_id},
        )
    view = await get_view_by_id(viewer_session, view_id)
    if view is None or view.binary_id != binary_id:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"View {view_id} does not belong to binary {binary_id}.",
            details={"viewId": view_id, "binaryId": binary_id},
        )
    await set_last_view_id(viewer_session, binary_id=binary_id, view_id=view_id)
    await viewer_session.commit()
