"""add_binary_analysis_image_base

Persist Ghidra's static image base captured during export. Function addresses
remain canonical static VAs; this nullable binary metadata permits a client to
translate an ASLR runtime VA for address lookup. Legacy exports retain NULL.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-27 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("binaries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("analysis_image_base", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("binaries", schema=None) as batch_op:
        batch_op.drop_column("analysis_image_base")