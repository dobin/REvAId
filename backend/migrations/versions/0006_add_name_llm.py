"""add_name_llm

C13 (auto-display variant): the LLM-proposed function name, via a nullable
`functions.name_llm sa.String()` column. LLM-owned like `summary_*` (never
touched by ingestion, A3) but participates in the display precedence
`name_analyst ?? name_llm ?? name_ghidra` — it never overwrites either
stored name. Deliberately **no CHECK constraint** — a plain `ADD COLUMN` is
safe on `functions` despite its VIRTUAL generated column
(`is_utility_effective`), same reasoning as migration 0005.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-25 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("functions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("name_llm", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("functions", schema=None) as batch_op:
        batch_op.drop_column("name_llm")
