"""kuna_schema_v4_kinds

Accept Kuna ``decompile-graph`` schema-v4's ``call``/``jump``/``data`` edge
kinds. SQLite requires a table rebuild to widen the edges CHECK constraint.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-05 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _edges_table(kind_check: str) -> sa.Table:
    return sa.Table(
        "edges",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("binary_id", sa.Integer(), nullable=False),
        sa.Column("caller_id", sa.Integer(), nullable=False),
        sa.Column("callee_id", sa.Integer(), nullable=False),
        sa.Column("callee_order", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.CheckConstraint(kind_check, name=op.f("ck_edges_kind_valid")),
        sa.CheckConstraint(
            "callee_order IS NULL OR callee_order >= 0",
            name=op.f("ck_edges_callee_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["binary_id"], ["binaries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["callee_id"], ["functions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["caller_id"], ["functions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edges")),
        sa.UniqueConstraint("caller_id", "callee_id", name="ux_edges_pair"),
    )


def _rebuild(kind_check: str) -> None:
    with op.batch_alter_table(
        "edges", schema=None, copy_from=_edges_table(kind_check), recreate="always"
    ):
        pass
    with op.batch_alter_table("edges", schema=None) as batch_op:
        batch_op.create_index("ix_edges_callee", ["callee_id"], unique=False)
        batch_op.create_index("ix_edges_caller", ["caller_id"], unique=False)
        batch_op.create_index(
            "ix_edges_caller_callee_order", ["caller_id", "callee_order"], unique=False
        )


def upgrade() -> None:
    _rebuild("kind IN ('call', 'jump', 'data')")


def downgrade() -> None:
    _rebuild("kind IN ('call')")