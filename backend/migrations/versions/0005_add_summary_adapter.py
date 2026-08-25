"""add_summary_adapter

I13 / AM4 (docs/specs/PLAN-I7-I8-I9-I13.md §6.1): record which LLM adapter
produced each summary, via a nullable `functions.summary_adapter TEXT`
column. Deliberately **no CHECK constraint** — a plain `ADD COLUMN` is safe
on `functions` despite its VIRTUAL generated column (`is_utility_effective`),
whereas a new CHECK would force a batch table rebuild SQLite refuses on this
table. Not surfaced in the UI yet (decision 6); the DTO exposes it so the
data is self-describing.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-25 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("functions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("summary_adapter", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("functions", schema=None) as batch_op:
        batch_op.drop_column("summary_adapter")
