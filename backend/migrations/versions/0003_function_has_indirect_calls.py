"""function_has_indirect_calls

I4/§5.1: add `functions.has_indirect_calls` — ground-truth/ingestion-owned
flag (persisted from `RawFunction.has_indirect_calls`, which existed since
I1/I2 but had no column to land in — see the `TODO(I4)` note in
`adapters/ghidra/base.py`). Feeds the `mayBeIncomplete` footer hint on a
function's callees neighbour page.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-21 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Plain (non-batch) ADD COLUMN — see 0002's note: batch mode's table
    # rebuild does an `INSERT INTO tmp SELECT ...` that SQLite rejects for a
    # table with a VIRTUAL generated column (`is_utility_effective`).
    op.add_column(
        "functions",
        sa.Column(
            "has_indirect_calls",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("functions", "has_indirect_calls")
