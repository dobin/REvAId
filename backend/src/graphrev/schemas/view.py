"""``GET /binaries/{id}/views`` DTOs.

Pulled forward, minimally, from I6's full view CRUD (TAD §4.2 #9): I5 only
needs to *resolve a viewId* to satisfy the required `viewId` query param on
`GET /functions/{id}/neighbours` (E2). Deliberately narrow — no `camera`, no
`nodes[]` — those belong to I6's full `ViewDto` (TAD §3.4).
"""

from __future__ import annotations

from graphrev.db.models import View
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
