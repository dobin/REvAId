"""move_last_view_to_ui_state

Revision ID: 0014
Revises: 0013
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fresh-schema baseline: `binaries.last_view_id` is no longer analysis
    # data. The independent viewer schema owns the preference table.
    with op.batch_alter_table("binaries", recreate="always") as batch_op:
        batch_op.drop_column("last_view_id")


def downgrade() -> None:
    with op.batch_alter_table("binaries", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("last_view_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_binaries_last_view_id_views",
            "views",
            ["last_view_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_table(
        "binary_ui_state",
        sa.Column("binary_id", sa.Integer(), nullable=False),
        sa.Column("last_view_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["last_view_id"],
            ["views.id"],
            ondelete="SET NULL",
            name="fk_binary_ui_state_last_view_id_views",
        ),
        sa.PrimaryKeyConstraint("binary_id", name="pk_binary_ui_state"),
    )
