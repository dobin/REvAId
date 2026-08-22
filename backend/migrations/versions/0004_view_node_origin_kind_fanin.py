"""view_node_origin_kind_fanin

I6/D8b: widen `view_nodes.origin_kind`'s CHECK constraint to admit `fanin`,
the provenance kind for leftward caller fan-out (a `fanin` node's derived
canvas edge is oriented new-node -> origin-card, so ELK direction RIGHT
places it to the *left* of the card it was spawned from).

SQLite cannot `ALTER TABLE ... DROP/ADD CONSTRAINT`, so widening a CHECK
requires a full table rebuild. Batch mode (`INSERT INTO tmp SELECT ...`) is
safe here — unlike 0002/0003, which avoid batch mode because `functions` has
a VIRTUAL generated column (`is_utility_effective`) that SQLite refuses to
copy; `view_nodes` has no generated column. `copy_from` is given an explicit
literal table definition because batch mode's reflection of SQLite CHECK
constraints is unreliable.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-22 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _view_nodes_table(check: str) -> sa.Table:
    """The `view_nodes` schema with a parameterised `origin_kind` CHECK.

    Used as `copy_from` for the batch rebuild so every constraint, FK, and
    unique key is preserved across the recreate — only the CHECK body differs
    between the upgrade (with `fanin`) and downgrade (without).
    """
    return sa.Table(
        "view_nodes",
        sa.MetaData(),
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
        sa.CheckConstraint(check, name=op.f("ck_view_nodes_origin_kind_valid")),
        sa.ForeignKeyConstraint(
            ["function_id"],
            ["functions.id"],
            name=op.f("fk_view_nodes_function_id_functions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["origin_function_id"],
            ["functions.id"],
            name=op.f("fk_view_nodes_origin_function_id_functions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["view_id"],
            ["views.id"],
            name=op.f("fk_view_nodes_view_id_views"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_view_nodes")),
        sa.UniqueConstraint(
            "view_id", "function_id", name="ux_view_nodes_view_id_function_id"
        ),
    )


_CHECK_WITH_FANIN = "origin_kind IN ('root', 'fanout', 'callstack', 'fanin')"
_CHECK_WITHOUT_FANIN = "origin_kind IN ('root', 'fanout', 'callstack')"


def _rebuild_with_check(check: str) -> None:
    """Recreate `view_nodes` with the given `origin_kind` CHECK, copying data.

    `copy_from` provides the *target* table shape (including the desired
    CHECK), and `recreate="always"` makes batch mode build a temp table from
    it, `INSERT INTO tmp SELECT ...` the existing rows, drop the original, and
    rename — preserving every row. The indexes are then re-declared, since
    batch mode does not reliably carry SQLite indexes across the rebuild.
    """
    with op.batch_alter_table(
        "view_nodes",
        schema=None,
        copy_from=_view_nodes_table(check),
        recreate="always",
    ):
        pass
    with op.batch_alter_table("view_nodes", schema=None) as batch_op:
        batch_op.create_index("ix_view_nodes_origin", ["origin_function_id"], unique=False)
        batch_op.create_index("ix_view_nodes_view", ["view_id", "visible"], unique=False)


def upgrade() -> None:
    _rebuild_with_check(_CHECK_WITH_FANIN)


def downgrade() -> None:
    _rebuild_with_check(_CHECK_WITHOUT_FANIN)
