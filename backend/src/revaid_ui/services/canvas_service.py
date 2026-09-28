"""Viewer canvas use cases backed by the analysis service contract.

The provenance invariant (D8b, B4b) is enforced here, at the service
boundary, not in the repository (which is "dumb SQL, no business rules" per
the TAD's layering principle #2) and not only in the DB (SQLite CHECK
constraints can enforce the closed `origin_kind` enum, but not the
cross-column "root implies no parent, fanout/callstack requires one" rule).
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from revaid_contracts.analysis import AnalysisClient, ResolvedFunction
from revaid_contracts.errors import ErrorCode
from revaid_contracts.http_errors import AppError
from revaid_ui.db.enums import PROVENANCE_ORIGIN_KIND_VALUES
from revaid_ui.repositories.view_nodes import remove_view_nodes, upsert_view_nodes
from revaid_ui.repositories.views import get_view_by_id, set_root_function_id
from revaid_ui.schemas.view import (
    OpenFunctionResultDto,
    OpenFunctionsRequestDto,
    OpenFunctionsResponseDto,
    ViewNodeDto,
    ViewNodesPatchRequestDto,
    ViewNodeUpsertDto,
    view_node_dto_from_row,
)

_ADDRESS_RE = re.compile(r"^(?:0[xX][0-9a-fA-F]+|[0-9]+)$")
_SQLITE_INTEGER_MAX = 2**63 - 1


def _parse_nonnegative_address(raw: str) -> int:
    value = raw.strip()
    if not _ADDRESS_RE.fullmatch(value):
        raise ValueError("Enter a decimal or 0x-prefixed hexadecimal address.")
    parsed = int(value, 16 if value.lower().startswith("0x") else 10)
    if parsed > _SQLITE_INTEGER_MAX:
        raise ValueError("Address exceeds the supported 64-bit signed integer range.")
    return parsed


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
    session: AsyncSession,
    analysis: AnalysisClient,
    *,
    view_id: int,
    request: ViewNodesPatchRequestDto,
) -> list[ViewNodeDto]:
    """Apply a batch upsert/remove, then return the full post-state of every
    node in the view (TAD's "so the client can reconcile" contract)."""
    view = await get_view_by_id(session, view_id)
    if view is None:
        raise AppError(ErrorCode.VIEW_NOT_FOUND, f"No view {view_id}.", details={"viewId": view_id})

    for entry in request.upsert:
        _validate_provenance(entry)

    referenced_ids = {
        function_id
        for entry in request.upsert
        for function_id in (entry.function_id, entry.origin_function_id)
        if function_id is not None
    }
    valid_ids = await analysis.validate_function_membership(view.binary_id, sorted(referenced_ids))
    if missing_ids := referenced_ids - valid_ids:
        missing_id = min(missing_ids)
        raise AppError(
            ErrorCode.FUNCTION_NOT_FOUND,
            f"No function {missing_id} in this view's binary.",
            details={"functionId": missing_id},
        )

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


async def open_functions(
    session: AsyncSession,
    analysis: AnalysisClient,
    *,
    view_id: int,
    request: OpenFunctionsRequestDto,
) -> OpenFunctionsResponseDto:
    """Translate runtime addresses, resolve functions, and place them atomically."""
    view = await get_view_by_id(session, view_id)
    if view is None:
        raise AppError(ErrorCode.VIEW_NOT_FOUND, f"No view {view_id}.", details={"viewId": view_id})

    binary = await analysis.get_binary(view.binary_id)
    if binary is None:
        raise AppError(ErrorCode.BINARY_NOT_FOUND, f"No binary {view.binary_id}.")
    if binary.analysis_image_base is None:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "This binary has no recorded analysis image base.",
            details={"binaryId": binary.id},
        )
    try:
        dll_base = _parse_nonnegative_address(request.dll_base)
    except ValueError as exc:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"Invalid DLL base: {exc}",
            details={"dllBase": request.dll_base},
        ) from exc

    existing_nodes = {node.function_id: node for node in view.nodes}
    available_ids = {node.function_id for node in view.nodes if node.visible}
    placed_ids: set[int] = set()
    upserts: list[dict[str, object]] = []
    results: list[OpenFunctionResultDto | None] = [None] * len(request.addresses)
    last_function_id: int | None = None

    resolved_entries: list[ResolvedFunction | None] = [None] * len(request.addresses)
    canonical_addresses: list[int] = []
    entry_canonical_addresses: list[int | None] = [None] * len(request.addresses)
    for index, raw in enumerate(request.addresses):
        try:
            runtime_address = _parse_nonnegative_address(raw)
            canonical_address = runtime_address - dll_base + binary.analysis_image_base
            if not 0 <= canonical_address <= _SQLITE_INTEGER_MAX:
                raise ValueError("Translated address is outside the supported range.")
        except ValueError as exc:
            results[index] = OpenFunctionResultDto(
                input_address=raw, status="invalid", message=str(exc)
            )
            continue

        if (
            binary.address_min is not None
            and binary.address_max is not None
            and not (binary.address_min <= canonical_address <= binary.address_max)
        ):
            results[index] = OpenFunctionResultDto(
                input_address=raw,
                status="unresolved",
                canonical_address=canonical_address,
                message=(
                    f"Translated address {canonical_address:#x} is outside this binary's "
                    "known function range; check the DLL load base."
                ),
            )
            continue
        canonical_addresses.append(canonical_address)
        entry_canonical_addresses[index] = canonical_address
        results[index] = OpenFunctionResultDto(
            input_address=raw,
            status="unresolved",
            canonical_address=canonical_address,
        )

    resolved_by_address = await analysis.resolve_addresses(view.binary_id, canonical_addresses)
    for index, maybe_canonical_address in enumerate(entry_canonical_addresses):
        if maybe_canonical_address is None:
            continue
        result_index = index
        canonical_address = maybe_canonical_address
        function = resolved_by_address.get(canonical_address)
        if function is None:
            results[result_index] = OpenFunctionResultDto(
                input_address=request.addresses[index],
                status="unresolved",
                canonical_address=canonical_address,
                message=f"No function contains {canonical_address:#x}.",
            )
            continue

        duplicate = function.id in placed_ids
        results[result_index] = OpenFunctionResultDto(
            input_address=request.addresses[index],
            status="duplicate" if duplicate else "resolved",
            canonical_address=canonical_address,
            function_id=function.id,
            display_name=function.display_name,
            message="Already resolved by an earlier address." if duplicate else None,
        )
        last_function_id = function.id
        resolved_entries[index] = function
        if duplicate:
            continue
        placed_ids.add(function.id)

    # Imported roots are considered in supplied order. Excluding all resolved
    # ids from the initial candidates prevents pre-existing disconnected roots
    # later in the list from pulling earlier frames backwards or forming a
    # provenance cycle; each frame becomes available after it is processed.
    available_ids -= placed_ids
    processed_ids: set[int] = set()
    for entry in resolved_entries:
        if entry is None:
            continue
        function_id = entry.id
        if function_id in processed_ids:
            continue
        processed_ids.add(function_id)

        origin = await analysis.find_canvas_origin(
            binary_id=view.binary_id,
            function_id=function_id,
            candidate_ids=available_ids,
        )
        existing = existing_nodes.get(function_id)
        if existing is not None:
            update: dict[str, object] = {"function_id": function_id}
            if not existing.visible:
                update["visible"] = True
            # A previous search/import may have placed this function as a
            # disconnected root. Now that a related visible/imported node is
            # available, repair that provenance so the canvas can render the
            # known call edge. Preserve deliberate non-root provenance.
            is_disconnected_root = existing.origin_function_id is None
            if is_disconnected_root and origin is not None:
                origin_function_id, origin_kind = origin
                update.update(
                    origin_function_id=origin_function_id,
                    origin_kind=origin_kind,
                    origin_implied=False,
                )
            if len(update) > 1:
                upserts.append(update)
        elif origin is None:
            upserts.append({"function_id": function_id, "visible": True, "origin_kind": "root"})
        else:
            origin_function_id, origin_kind = origin
            upserts.append(
                {
                    "function_id": function_id,
                    "visible": True,
                    "origin_function_id": origin_function_id,
                    "origin_kind": origin_kind,
                    "origin_implied": False,
                }
            )
        available_ids.add(function_id)

    if upserts:
        await upsert_view_nodes(session, view_id=view_id, upserts=upserts)
    if last_function_id is not None:
        await set_root_function_id(session, view, last_function_id)
    await session.commit()
    await session.refresh(view, attribute_names=["nodes"])
    # Refresh scalar fields on identity-mapped children too. Refreshing only
    # the relationship collection does not overwrite an existing ViewNode's
    # cached provenance after an UPSERT, which otherwise returns stale roots
    # even though the database row was connected correctly.
    for node in view.nodes:
        await session.refresh(node)
    return OpenFunctionsResponseDto(
        results=[result for result in results if result is not None],
        nodes=[view_node_dto_from_row(node) for node in view.nodes],
        root_function_id=(
            last_function_id if last_function_id is not None else view.root_function_id
        ),
    )
