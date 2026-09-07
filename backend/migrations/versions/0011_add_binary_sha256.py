"""add_binary_sha256

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-07 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("binaries", sa.Column("sha256", sa.String(), nullable=True))
    op.create_index("ix_binaries_sha256", "binaries", ["sha256"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_binaries_sha256", table_name="binaries")
    op.drop_column("binaries", "sha256")