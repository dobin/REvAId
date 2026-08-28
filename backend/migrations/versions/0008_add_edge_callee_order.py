"""add_edge_callee_order

Persist the static first-call-site order emitted as ``calleeOrder`` by the
schema-v2 Ghidra exporter. Legacy/schema-v1 edges remain NULL: zero is a
meaningful first-callee ordinal and must never be fabricated as a default.

SQLite needs a table rebuild to add the non-negative CHECK constraint. Unlike
``functions``, ``edges`` has no generated column, so batch copy is safe.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-28 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _edges_table(*, with_callee_order: bool) -> sa.Table:
    columns = [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("binary_id", sa.Integer(), nullable=False),
        sa.Column("caller_id", sa.Integer(), nullable=False),
        sa.Column("callee_id", sa.Integer(), nullable=False),
    ]
    if with_callee_order:
        columns.append(sa.Column("callee_order", sa.Integer(), nullable=True))
    columns.append(sa.Column("kind", sa.String(), nullable=False))

    constraints: list[sa.SchemaItem] = [
        sa.CheckConstraint("kind IN ('call')", name=op.f("ck_edges_kind_valid")),
        sa.ForeignKeyConstraint(
            ["binary_id"], ["binaries.id"], name=op.f("fk_edges_binary_id_binaries"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["callee_id"], ["functions.id"], name=op.f("fk_edges_callee_id_functions"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["caller_id"], ["functions.id"], name=op.f("fk_edges_caller_id_functions"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_edges")),
        sa.UniqueConstraint("caller_id", "callee_id", name="ux_edges_pair"),
    ]
    if with_callee_order:
        constraints.append(
            sa.CheckConstraint(
                "callee_order IS NULL OR callee_order >= 0",
                name=op.f("ck_edges_callee_order_nonnegative"),
            )
        )
    return sa.Table("edges", sa.MetaData(), *columns, *constraints)


def _rebuild_edges(*, with_callee_order: bool) -> None:
    with op.batch_alter_table(
        "edges", schema=None, copy_from=_edges_table(with_callee_order=with_callee_order), recreate="always"
    ):
        pass
    with op.batch_alter_table("edges", schema=None) as batch_op:
        batch_op.create_index("ix_edges_callee", ["callee_id"], unique=False)
        batch_op.create_index("ix_edges_caller", ["caller_id"], unique=False)
        if with_callee_order:
            batch_op.create_index(
                "ix_edges_caller_callee_order", ["caller_id", "callee_order"], unique=False
            )


def upgrade() -> None:
    # Add first so the batch copy can select the legacy rows' new NULL column
    # into the explicit target table definition below.
    with op.batch_alter_table("edges", schema=None) as batch_op:
        batch_op.add_column(sa.Column("callee_order", sa.Integer(), nullable=True))
    _rebuild_edges(with_callee_order=True)


def downgrade() -> None:
    _rebuild_edges(with_callee_order=False)