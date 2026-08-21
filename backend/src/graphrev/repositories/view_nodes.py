"""``view_nodes`` repository: batch upsert/remove (TAD §4.3 #12, I6).

Idempotent UPSERT keyed on ``ux_view_nodes(view_id, function_id)``, same
SQLite ``ON CONFLICT`` idiom as ``repositories/functions.py::upsert_function``.
Unlike the ingestion UPSERT (which never overwrites analyst-owned columns),
every column here is client-owned — a partial patch only omits fields that
should stay untouched, it never protects a column category the way
``INGESTION_OWNED_COLUMNS`` does.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from graphrev.core.clock import utc_now_iso
from graphrev.db.models import ViewNode

__all__ = ["list_nodes_by_view", "remove_view_nodes", "upsert_view_nodes"]


async def list_nodes_by_view(session: AsyncSession, *, view_id: int) -> list[ViewNode]:
    result = await session.execute(select(ViewNode).where(ViewNode.view_id == view_id))
    return list(result.scalars().all())


#: Defaults applied only on first INSERT (never on conflict-update) for a
#: field omitted from an upsert entry — matches the DB column defaults in
#: ``db/models.py`` so a brand-new node behaves identically whether it is
#: created by ingestion-adjacent code or by this batch endpoint.
_NEW_ROW_DEFAULTS: dict[str, object] = {
    "visible": True,
    "collapsed": False,
    "color": None,
    "pos_x": 0.0,
    "pos_y": 0.0,
    "pinned": False,
    "origin_function_id": None,
    "origin_kind": "root",
    "origin_implied": False,
}


async def upsert_view_nodes(
    session: AsyncSession,
    *,
    view_id: int,
    upserts: list[dict[str, object]],
) -> None:
    """Batch upsert. Each dict must contain ``function_id``; every other key
    is optional and, when present, is written for both INSERT and UPDATE.
    Fields omitted on UPDATE are left as-is (SQLite's ``excluded`` is only
    referenced for keys actually present in the values, via a per-row
    ``on_conflict_do_update`` — since each row's field set can differ, this
    upserts one row at a time rather than a single multi-row statement)."""
    now = utc_now_iso()
    for entry in upserts:
        function_id = entry["function_id"]
        provided = {k: v for k, v in entry.items() if k != "function_id"}

        values: dict[str, object] = {
            "view_id": view_id,
            "function_id": function_id,
            "created_at": now,
            "updated_at": now,
            **_NEW_ROW_DEFAULTS,
            **provided,
        }
        update_set = {**provided, "updated_at": now}

        stmt = sqlite_insert(ViewNode).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ViewNode.view_id, ViewNode.function_id],
            set_=update_set,
        )
        await session.execute(stmt)
    await session.flush()


async def remove_view_nodes(
    session: AsyncSession, *, view_id: int, function_ids: list[int]
) -> None:
    """Hard-delete the given ``(view_id, function_id)`` rows. Scoped to
    ``view_id`` so a stray id never removes a node from the wrong view."""
    if not function_ids:
        return
    await session.execute(
        delete(ViewNode).where(
            ViewNode.view_id == view_id, ViewNode.function_id.in_(function_ids)
        )
    )
    await session.flush()
