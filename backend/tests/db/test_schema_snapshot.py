"""The keystone I1 test: models and migration must agree exactly.

Two assertions:
  1. After `alembic upgrade head`, the live SQLite schema has the expected
     tables/columns/indexes/constraints (a normalised structural snapshot).
  2. Alembic's own autogenerate against `Base.metadata` produces an empty
     diff — i.e. nothing has drifted between `db/models.py` and
     `migrations/versions/0001_initial.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine

from revaid.db.models import Base
from revaid_ui.db.models import ViewerBase

EXPECTED_TABLES = {
    "alembic_version",
    "app_meta",
    "binaries",
    "functions",
    "llm_worker_statuses",
    "edges",
    "data_items",
    "data_refs",
}


@pytest.mark.asyncio
async def test_all_expected_tables_exist(engine: AsyncEngine, migrated_db: Path) -> None:
    async with engine.connect() as conn:

        def _table_names(sync_conn: object) -> list[str]:
            return inspect(sync_conn).get_table_names()  # type: ignore[arg-type]

        tables = await conn.run_sync(_table_names)
    assert set(tables) == EXPECTED_TABLES


@pytest.mark.asyncio
async def test_functions_columns_match_model(engine: AsyncEngine, migrated_db: Path) -> None:
    expected_columns = {c.name for c in Base.metadata.tables["functions"].columns}
    async with engine.connect() as conn:

        def _columns(sync_conn: object) -> list[str]:
            return [c["name"] for c in inspect(sync_conn).get_columns("functions")]  # type: ignore[arg-type]

        columns = await conn.run_sync(_columns)
    assert set(columns) == expected_columns


@pytest.mark.asyncio
async def test_is_featured_is_non_nullable_and_defaults_false(
    engine: AsyncEngine, migrated_db: Path
) -> None:
    async with engine.connect() as conn:

        def _columns(sync_conn: object) -> list[dict[str, object]]:
            return inspect(sync_conn).get_columns("functions")  # type: ignore[arg-type,return-value]

        columns = await conn.run_sync(_columns)
    column = next(column for column in columns if column["name"] == "is_featured")
    assert column["nullable"] is False
    assert str(column["default"]) in {"0", "false", "(0)"}


@pytest.mark.asyncio
async def test_edges_columns_match_model(engine: AsyncEngine, migrated_db: Path) -> None:
    expected_columns = {c.name for c in Base.metadata.tables["edges"].columns}
    async with engine.connect() as conn:

        def _columns(sync_conn: object) -> list[str]:
            return [c["name"] for c in inspect(sync_conn).get_columns("edges")]  # type: ignore[arg-type]

        columns = await conn.run_sync(_columns)
    assert set(columns) == expected_columns


@pytest.mark.asyncio
async def test_binaries_columns_match_model(engine: AsyncEngine, migrated_db: Path) -> None:
    expected_columns = {c.name for c in Base.metadata.tables["binaries"].columns}
    async with engine.connect() as conn:

        def _columns(sync_conn: object) -> list[str]:
            return [c["name"] for c in inspect(sync_conn).get_columns("binaries")]  # type: ignore[arg-type]

        columns = await conn.run_sync(_columns)
    assert set(columns) == expected_columns


@pytest.mark.asyncio
async def test_analysis_database_excludes_viewer_state(
    engine: AsyncEngine, migrated_db: Path
) -> None:
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
    assert "binary_ui_state" not in tables
    assert "views" not in tables
    assert "view_nodes" not in tables


@pytest.mark.asyncio
async def test_viewer_database_has_no_external_foreign_keys(
    viewer_engine: AsyncEngine, viewer_migrated_db: Path
) -> None:
    assert set(ViewerBase.metadata.tables) == {"binary_ui_state", "views", "view_nodes"}
    async with viewer_engine.connect() as conn:
        state_fks = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_foreign_keys("binary_ui_state")
        )
        view_fks = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_foreign_keys("views")
        )
        node_fks = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_foreign_keys("view_nodes")
        )
    assert state_fks == []
    assert view_fks == []
    assert len(node_fks) == 1
    assert node_fks[0]["constrained_columns"] == ["view_id"]
    assert node_fks[0]["referred_table"] == "views"


@pytest.mark.asyncio
async def test_viewer_autogenerate_diff_is_empty(
    viewer_engine: AsyncEngine, viewer_migrated_db: Path
) -> None:
    async with viewer_engine.connect() as conn:

        def _diff(sync_conn: object) -> list[object]:
            context = MigrationContext.configure(sync_conn)  # type: ignore[arg-type]
            return compare_metadata(context, ViewerBase.metadata)

        diff = await conn.run_sync(_diff)

    assert diff == [], f"Viewer model/migration drift detected: {diff!r}"


@pytest.mark.asyncio
async def test_analysis_autogenerate_diff_is_empty(engine: AsyncEngine, migrated_db: Path) -> None:
    async with engine.connect() as conn:

        def _diff(sync_conn: object) -> list[object]:
            context = MigrationContext.configure(sync_conn)  # type: ignore[arg-type]
            return compare_metadata(context, Base.metadata)

        diff = await conn.run_sync(_diff)

    assert diff == [], f"Analysis model/migration drift detected: {diff!r}"


@pytest.mark.asyncio
async def test_indexes_present(engine: AsyncEngine, migrated_db: Path) -> None:
    async with engine.connect() as conn:

        def _index_names(sync_conn: object) -> set[str]:
            insp = inspect(sync_conn)
            names: set[str] = set()
            for table in ("binaries", "functions", "edges"):
                names |= {ix["name"] for ix in insp.get_indexes(table)}  # type: ignore[arg-type]
            return names

        index_names = await conn.run_sync(_index_names)

    expected = {
        "ix_binaries_sha256",
        "ix_functions_binary_name",
        "ix_functions_binary_analystname",
        "ix_functions_status",
        "ix_functions_fanin",
        "ix_functions_utility_eff",
        "ix_edges_caller",
        "ix_edges_callee",
        "ix_edges_caller_callee_order",
    }
    assert expected <= index_names


@pytest.mark.asyncio
async def test_autogenerate_diff_is_empty(engine: AsyncEngine, migrated_db: Path) -> None:
    """The empty-diff guarantee: `alembic revision --autogenerate` after
    `upgrade head` must detect zero changes, i.e. models and migrations agree.
    """

    async with engine.connect() as conn:

        def _diff(sync_conn: object) -> list[object]:
            context = MigrationContext.configure(sync_conn)  # type: ignore[arg-type]
            return compare_metadata(context, Base.metadata)

        diff = await conn.run_sync(_diff)

    assert diff == [], f"Model/migration drift detected: {diff!r}"
