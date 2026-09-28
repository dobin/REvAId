"""Create viewer-owned binary preferences.

Revision ID: viewer_0001
Revises:
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "viewer_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "binary_ui_state",
        sa.Column("binary_id", sa.Integer(), nullable=False),
        sa.Column("last_view_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("binary_id", name="pk_binary_ui_state"),
    )


def downgrade() -> None:
    op.drop_table("binary_ui_state")
