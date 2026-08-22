"""Canvas use cases — provenance invariants + batch node patch (TAD §4.3 #12).

The provenance invariant (D8b, B4b) is enforced here, at the service
boundary, not in the repository (which is "dumb SQL, no business rules" per
the TAD's layering principle #2) and not only in the DB (SQLite CHECK
constraints can enforce the closed `origin_kind` enum, but not the
cross-column "root implies no parent, fanout/callstack requires one" rule).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.errors import AppError, ErrorCode
from graphrev.db.enums import PROVENANCE_ORIGIN_KIND_VALUES
from graphrev.repositories.view_nodes import remove_view_nodes, upsert_view_nodes
from graphrev.repositories.views import get_view_by_id
from graphrev.schemas.view import (
    ViewNodeDto,
    ViewNodesPatchRequestDto,
    ViewNodeUpsertDto,
    view_node_dto_from_row,
)


def _validate_provenance(upsert_dto: ViewNodeUpsertDto) -> None:
    """D8b: `origin_kind == "root"` <=> `origin_function_id is None`.

    A request that sets `origin_kind` to a non-root value must also supply a
    non-null `origin_function_id` *in the same request* — this endpoint has
    no way to know an existing row's current `origin_function_id` without an
    extra read, and requiring both together in one PATCH is the simplest
    rule that can never leave a row in an invalid state. Conversely, setting
    `origin_kind` to `"root"` while also supplying a non-null
    `origin_function_id` is rejected outright, regardless of any existing
    row. Neither field being touched at all — a partial patch of some other
    field — skips this check entirely.
    """
    fields_set = upsert_dto.model_fields_set
    origin_kind = upsert_dto.origin_kind
    origin_function_id = upsert_dto.origin_function_id

    if "origin_kind" in fields_set:
        if origin_kind == "root" and origin_function_id is not None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "A root node must not have an originFunctionId.",
                details={"functionId": upsert_dto.function_id},
            )
        if origin_kind in PROVENANCE_ORIGIN_KIND_VALUES and (
            "origin_function_id" not in fields_set or origin_function_id is None
        ):
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                f"A '{origin_kind}' node requires an originFunctionId.",
                details={"functionId": upsert_dto.function_id},
            )
    elif "origin_function_id" in fields_set and origin_function_id is not None:
        # origin_function_id is being set without origin_kind in this same
        # request: only valid if the row (new or existing) will end up with
        # a non-root origin_kind. We cannot know an existing row's kind
        # without an extra read; a brand-new row defaults to "root", which
        # would violate the invariant, so this combination is rejected too.
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "originFunctionId requires originKind to be a non-root provenance"
            " kind (fanout, callstack, or fanin) in the same request.",
            details={"functionId": upsert_dto.function_id},
        )


async def patch_view_nodes(
    session: AsyncSession, *, view_id: int, request: ViewNodesPatchRequestDto
) -> list[ViewNodeDto]:
    """Apply a batch upsert/remove, then return the full post-state of every
    node in the view (TAD's "so the client can reconcile" contract)."""
    view = await get_view_by_id(session, view_id)
    if view is None:
        raise AppError(
            ErrorCode.VIEW_NOT_FOUND, f"No view {view_id}.", details={"viewId": view_id}
        )

    for entry in request.upsert:
        _validate_provenance(entry)

    upsert_dicts = [
        entry.model_dump(exclude_unset=True, by_alias=False) for entry in request.upsert
    ]
    if upsert_dicts:
        await upsert_view_nodes(session, view_id=view_id, upserts=upsert_dicts)
    if request.remove:
        await remove_view_nodes(session, view_id=view_id, function_ids=request.remove)

    await session.commit()

    # `view` is already identity-mapped in this session with `.nodes`
    # eager-loaded from the fetch above; a second `get_view_by_id` query
    # would return the *same* Python object without refreshing that
    # already-loaded collection, so the freshly upserted/removed rows must
    # be pulled in via an explicit refresh instead of a re-query.
    await session.refresh(view, attribute_names=["nodes"])
    return [view_node_dto_from_row(n) for n in view.nodes]
