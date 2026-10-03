"""add_data_item_summary_llm

Add an optional agent-authored summary to indexed PE data items.

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("data_items", sa.Column("summary_llm", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("data_items", "summary_llm")
