"""Drop canvas tables from the analysis database.

Revision ID: 0015
Revises: 0014
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("view_nodes")
    op.drop_index("ix_views_binary", table_name="views")
    op.drop_table("views")


def downgrade() -> None:
    raise RuntimeError("Analysis canvas tables are viewer-owned; downgrade is unsupported.")
