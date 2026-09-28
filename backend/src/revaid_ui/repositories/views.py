"""Viewer-owned view, canvas, and last-view state repository."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from revaid_ui.core.clock import utc_now_iso
from revaid_ui.db.models import BinaryUiState, View, ViewNode

__all__ = [
    "clear_last_view_id",
    "clear_last_view_ids_for_view",
    "count_views_by_binary",
    "create_view",
    "delete_view",
    "delete_views_by_binary",
    "duplicate_view",
    "get_last_view_ids",
    "get_view_by_id",
    "list_views_by_binary",
    "set_last_view_id",
    "update_view_fields",
]


async def list_views_by_binary(session: AsyncSession, *, binary_id: int) -> list[View]:
    """All views for `binary_id`, ordered by id (creation order)."""
    result = await session.execute(
        select(View).where(View.binary_id == binary_id).order_by(View.id)
    )
    return list(result.scalars().all())


async def count_views_by_binary(session: AsyncSession, *, binary_id: int) -> int:
    result = await session.execute(select(func.count(View.id)).where(View.binary_id == binary_id))
    return result.scalar_one()


async def get_last_view_ids(session: AsyncSession, *, binary_ids: list[int]) -> dict[int, int]:
    """Get viewer-owned last-view preferences for requested analysis IDs."""
    if not binary_ids:
        return {}
    rows = await session.execute(
        select(BinaryUiState.binary_id, BinaryUiState.last_view_id).where(
            BinaryUiState.binary_id.in_(binary_ids), BinaryUiState.last_view_id.is_not(None)
        )
    )
    return {binary_id: view_id for binary_id, view_id in rows if view_id is not None}


async def set_last_view_id(session: AsyncSession, *, binary_id: int, view_id: int) -> None:
    """Write a viewer-local last-view preference."""
    state = await session.get(BinaryUiState, binary_id)
    now = utc_now_iso()
    if state is None:
        session.add(BinaryUiState(binary_id=binary_id, last_view_id=view_id, updated_at=now))
    else:
        state.last_view_id = view_id
        state.updated_at = now
    await session.flush()


async def clear_last_view_id(session: AsyncSession, *, binary_id: int) -> None:
    """Clear a stale last-view reference for one analysis binary ID."""
    state = await session.get(BinaryUiState, binary_id)
    if state is not None:
        await session.delete(state)
        await session.flush()


async def clear_last_view_ids_for_view(session: AsyncSession, *, view_id: int) -> None:
    """Clear preferences that refer to a deleted viewer view."""
    await session.execute(delete(BinaryUiState).where(BinaryUiState.last_view_id == view_id))
    await session.flush()


async def create_view(
    session: AsyncSession, *, binary_id: int, name: str, view_id: int | None = None
) -> View:
    """Create a `View` row.

    `view_id` is normally left ``None`` so SQLite assigns the next
    autoincrement id; public mode passes an explicit random id (ADR 0006)
    so view ids are unguessable capabilities, not enumerable ints.
    """
    now = utc_now_iso()
    view = View(
        binary_id=binary_id,
        name=name,
        root_function_id=None,
        camera_x=0.0,
        camera_y=0.0,
        camera_zoom=1.0,
        created_at=now,
        updated_at=now,
    )
    if view_id is not None:
        view.id = view_id
    session.add(view)
    await session.flush()
    return view


async def get_view_by_id(session: AsyncSession, view_id: int) -> View | None:
    """A single `View` row with its `nodes` eager-loaded (the DTO mapper has
    no session and must not lazy-load)."""
    result = await session.execute(
        select(View).where(View.id == view_id).options(selectinload(View.nodes))
    )
    return result.scalar_one_or_none()


async def update_view_fields(
    session: AsyncSession,
    view: View,
    *,
    name: str | None = None,
    camera_x: float | None = None,
    camera_y: float | None = None,
    camera_zoom: float | None = None,
) -> View:
    """Only touches fields explicitly passed; `None` means "leave unchanged"
    for every field here. `root_function_id` is genuinely nullable on the
    wire (B10a: "may be NULL for an empty view"), so it is never mixed into
    this "None means unchanged" convention — use `set_root_function_id`."""
    if name is not None:
        view.name = name
    if camera_x is not None:
        view.camera_x = camera_x
    if camera_y is not None:
        view.camera_y = camera_y
    if camera_zoom is not None:
        view.camera_zoom = camera_zoom
    view.updated_at = utc_now_iso()
    await session.flush()
    return view


async def set_root_function_id(
    session: AsyncSession, view: View, root_function_id: int | None
) -> View:
    """Separate setter because `None` is a legitimate value for
    `root_function_id` (B10a), unlike the other optional fields above."""
    view.root_function_id = root_function_id
    view.updated_at = utc_now_iso()
    await session.flush()
    return view


async def delete_view(session: AsyncSession, view: View) -> None:
    await session.delete(view)
    await session.flush()


async def delete_views_by_binary(session: AsyncSession, *, binary_id: int) -> None:
    """Delete viewer-owned canvases and preferences for an external binary ID."""
    view_ids = select(View.id).where(View.binary_id == binary_id)
    await session.execute(delete(ViewNode).where(ViewNode.view_id.in_(view_ids)))
    await session.execute(delete(View).where(View.binary_id == binary_id))
    await session.execute(delete(BinaryUiState).where(BinaryUiState.binary_id == binary_id))
    await session.flush()


async def duplicate_view(session: AsyncSession, view: View, *, view_id: int | None = None) -> View:
    """Copy layout only (B8): a new `View` row plus a verbatim copy of every
    `ViewNode` row (new ids, same positions/colors/provenance). No summaries
    or functions are touched. `view_id` is an explicit random id in public
    mode (ADR 0006), else autoincrement."""
    now = utc_now_iso()
    new_view = View(
        binary_id=view.binary_id,
        name=f"{view.name} (copy)",
        root_function_id=view.root_function_id,
        camera_x=view.camera_x,
        camera_y=view.camera_y,
        camera_zoom=view.camera_zoom,
        created_at=now,
        updated_at=now,
    )
    if view_id is not None:
        new_view.id = view_id
    session.add(new_view)
    await session.flush()

    for node in view.nodes:
        session.add(
            ViewNode(
                view_id=new_view.id,
                function_id=node.function_id,
                visible=node.visible,
                collapsed=node.collapsed,
                color=node.color,
                pos_x=node.pos_x,
                pos_y=node.pos_y,
                pinned=node.pinned,
                origin_function_id=node.origin_function_id,
                origin_kind=node.origin_kind,
                origin_implied=node.origin_implied,
                created_at=now,
                updated_at=now,
            )
        )
    await session.flush()
    await session.refresh(new_view, attribute_names=["nodes"])
    return new_view
