"""add_function_is_featured

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A plain ADD COLUMN is compatible with SQLite's VIRTUAL generated
    # `is_utility_effective` column; batch table rebuilding is not.
    op.add_column(
        "functions",
        sa.Column(
            "is_featured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("functions", "is_featured")
