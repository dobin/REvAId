"""Create viewer-owned canvas tables with only local foreign keys.

Revision ID: viewer_0002
Revises: viewer_0001
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "viewer_0002"
down_revision: str | Sequence[str] | None = "viewer_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "views",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("binary_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("root_function_id", sa.Integer(), nullable=True),
        sa.Column("camera_x", sa.Float(), nullable=False),
        sa.Column("camera_y", sa.Float(), nullable=False),
        sa.Column("camera_zoom", sa.Float(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_views"),
    )
    op.create_index("ix_views_binary", "views", ["binary_id"])
    op.create_table(
        "view_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("view_id", sa.Integer(), nullable=False),
        sa.Column("function_id", sa.Integer(), nullable=False),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column("collapsed", sa.Boolean(), nullable=False),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("pos_x", sa.Float(), nullable=False),
        sa.Column("pos_y", sa.Float(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("origin_function_id", sa.Integer(), nullable=True),
        sa.Column("origin_kind", sa.String(), nullable=False),
        sa.Column("origin_implied", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "origin_kind IN ('root', 'fanout', 'callstack', 'fanin')",
            name="origin_kind_valid",
        ),
        sa.ForeignKeyConstraint(
            ["view_id"],
            ["views.id"],
            ondelete="CASCADE",
            name="fk_view_nodes_view_id_views",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_view_nodes"),
        sa.UniqueConstraint("view_id", "function_id", name="ux_view_nodes_view_id_function_id"),
    )
    op.create_index("ix_view_nodes_view", "view_nodes", ["view_id", "visible"])
    op.create_index("ix_view_nodes_origin", "view_nodes", ["origin_function_id"])


def downgrade() -> None:
    op.drop_index("ix_view_nodes_origin", table_name="view_nodes")
    op.drop_index("ix_view_nodes_view", table_name="view_nodes")
    op.drop_table("view_nodes")
    op.drop_index("ix_views_binary", table_name="views")
    op.drop_table("views")
