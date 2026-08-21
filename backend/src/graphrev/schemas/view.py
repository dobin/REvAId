"""``/views`` and ``/views/{id}/nodes`` DTOs (TAD §3.4, §4.2 #9-#12).

``ViewSummaryDto`` was pulled forward to I5 as a narrow stopgap; it stays as
is (still used by the ``GET /binaries/{id}/views`` listing). Everything below
it -- the full ``ViewDto`` with ``camera``/``nodes[]``, ``ViewNodeDto``, and
the create/patch/batch-node-patch request DTOs -- is I6 scope.
"""

from __future__ import annotations

from pydantic import Field

from graphrev.db.enums import OriginKind
from graphrev.db.models import View, ViewNode
from graphrev.schemas.common import ApiModel


class ViewSummaryDto(ApiModel):
    id: int
    binary_id: int
    name: str
    root_function_id: int | None
    created_at: str
    updated_at: str


def view_summary_from_view(view: View) -> ViewSummaryDto:
    return ViewSummaryDto(
        id=view.id,
        binary_id=view.binary_id,
        name=view.name,
        root_function_id=view.root_function_id,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


class ViewNodeDto(ApiModel):
    """One placed node (TAD §3.4). ``functionId`` is the stable identity key
    the client reconciles on -- there is no separate node id on the wire."""

    function_id: int
    visible: bool
    collapsed: bool
    color: str | None
    pos_x: float
    pos_y: float
    pinned: bool
    origin_function_id: int | None
    origin_kind: OriginKind
    origin_implied: bool


def view_node_dto_from_row(node: ViewNode) -> ViewNodeDto:
    return ViewNodeDto(
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
    )


class CameraDto(ApiModel):
    x: float
    y: float
    zoom: float


class ViewDto(ApiModel):
    """The full view record (TAD §3.4) -- ``GET /views/{id}``'s response, and
    the response shape for create/patch/duplicate."""

    id: int
    binary_id: int
    name: str
    root_function_id: int | None
    camera: CameraDto
    nodes: list[ViewNodeDto]
    created_at: str
    updated_at: str


def view_dto_from_view(view: View) -> ViewDto:
    """Requires ``view.nodes`` to already be loaded (eager-loaded by the
    repository, never lazy-loaded here -- this module has no session)."""
    return ViewDto(
        id=view.id,
        binary_id=view.binary_id,
        name=view.name,
        root_function_id=view.root_function_id,
        camera=CameraDto(x=view.camera_x, y=view.camera_y, zoom=view.camera_zoom),
        nodes=[view_node_dto_from_row(n) for n in view.nodes],
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


class ViewCreateDto(ApiModel):
    """``POST /binaries/{id}/views`` request body (B8/B9)."""

    name: str


class ViewPatchDto(ApiModel):
    """``PATCH /views/{id}`` request body (E3a) -- name/root/camera, all
    optional-and-absent-means-"leave unchanged" (``model_fields_set``, same
    idiom as ``FunctionUpdateDto``)."""

    name: str | None = None
    root_function_id: int | None = None
    camera: CameraDto | None = None


class ViewNodeUpsertDto(ApiModel):
    """One entry in the ``upsert`` array of the batch node-patch request
    (TAD §4.3 #12). Every field but ``functionId`` is optional: a partial
    patch of an existing row leaves omitted fields untouched; a brand-new row
    gets the repository-level defaults for anything omitted."""

    function_id: int
    visible: bool | None = None
    collapsed: bool | None = None
    color: str | None = None
    pos_x: float | None = None
    pos_y: float | None = None
    pinned: bool | None = None
    origin_function_id: int | None = None
    origin_kind: OriginKind | None = None
    origin_implied: bool | None = None


class ViewNodesPatchRequestDto(ApiModel):
    """``PATCH /views/{id}/nodes`` request body (E3)."""

    upsert: list[ViewNodeUpsertDto] = Field(default_factory=list)
    remove: list[int] = Field(default_factory=list)


class ViewNodesPatchResponseDto(ApiModel):
    """The full post-state of every node in the view, so the client can
    reconcile (TAD §4.3 #12)."""

    nodes: list[ViewNodeDto]


class SetLastViewRequestDto(ApiModel):
    """``POST /binaries/{id}/last-view`` request body (B16, I6). A dedicated
    endpoint rather than a side effect of ``GET /views/{id}`` — GETs stay
    side-effect free everywhere in this API."""

    view_id: int
