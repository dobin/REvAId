"""rename_function_name

Rename the ingestion-owned function name column from ``name_ghidra`` to
``name``. The existing ``ix_functions_binary_name`` index keeps its public
name and is rebuilt against the renamed column for consistent SQLite and
non-SQLite behavior.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-16 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Use SQLite's native RENAME COLUMN support instead of batch mode: batch
    # table recreation cannot copy the existing VIRTUAL generated column.
    op.drop_index("ix_functions_binary_name", table_name="functions")
    op.alter_column("functions", "name_ghidra", new_column_name="name")
    op.create_index("ix_functions_binary_name", "functions", ["binary_id", "name"])


def downgrade() -> None:
    op.drop_index("ix_functions_binary_name", table_name="functions")
    op.alter_column("functions", "name", new_column_name="name_ghidra")
    op.create_index(
        "ix_functions_binary_name", "functions", ["binary_id", "name_ghidra"]
    )
