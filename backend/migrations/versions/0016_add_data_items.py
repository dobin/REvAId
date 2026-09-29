"""add_data_items

PE data items (.data/.rdata/...) referenced from function assembly and the
function -> data references, populated on raw-binary import.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-29 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("binary_id", sa.Integer(), nullable=False),
        sa.Column("address", sa.Integer(), nullable=False),
        sa.Column("rva", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("value_text", sa.String(), nullable=True),
        sa.Column("target_address", sa.Integer(), nullable=True),
        sa.Column("preview_hex", sa.String(), nullable=True),
        sa.Column("is_writable", sa.Boolean(), nullable=False),
        sa.Column("ref_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('string', 'wstring', 'pointer', 'import', 'bytes', 'uninitialized')",
            name=op.f("ck_data_items_kind_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["binary_id"],
            ["binaries.id"],
            name=op.f("fk_data_items_binary_id_binaries"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_items")),
        sa.UniqueConstraint("binary_id", "address", name="ux_data_items_binary_address"),
    )
    op.create_index("ix_data_items_binary_kind", "data_items", ["binary_id", "kind"])
    op.create_index("ix_data_items_binary_section", "data_items", ["binary_id", "section"])
    op.create_index("ix_data_items_binary_refcount", "data_items", ["binary_id", "ref_count"])

    op.create_table(
        "data_refs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("binary_id", sa.Integer(), nullable=False),
        sa.Column("function_id", sa.Integer(), nullable=False),
        sa.Column("data_item_id", sa.Integer(), nullable=False),
        sa.Column("instruction_address", sa.Integer(), nullable=False),
        sa.Column("instruction_text", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["binary_id"],
            ["binaries.id"],
            name=op.f("fk_data_refs_binary_id_binaries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["function_id"],
            ["functions.id"],
            name=op.f("fk_data_refs_function_id_functions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["data_item_id"],
            ["data_items.id"],
            name=op.f("fk_data_refs_data_item_id_data_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_refs")),
        sa.UniqueConstraint(
            "function_id",
            "data_item_id",
            "instruction_address",
            name="ux_data_refs_function_item_instruction",
        ),
    )
    op.create_index("ix_data_refs_item", "data_refs", ["data_item_id"])
    op.create_index("ix_data_refs_function", "data_refs", ["function_id"])
    op.create_index("ix_data_refs_binary", "data_refs", ["binary_id"])


def downgrade() -> None:
    op.drop_index("ix_data_refs_binary", table_name="data_refs")
    op.drop_index("ix_data_refs_function", table_name="data_refs")
    op.drop_index("ix_data_refs_item", table_name="data_refs")
    op.drop_table("data_refs")
    op.drop_index("ix_data_items_binary_refcount", table_name="data_items")
    op.drop_index("ix_data_items_binary_section", table_name="data_items")
    op.drop_index("ix_data_items_binary_kind", table_name="data_items")
    op.drop_table("data_items")
