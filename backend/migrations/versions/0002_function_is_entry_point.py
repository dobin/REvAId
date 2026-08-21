"""function_is_entry_point

I3/E1b: add `functions.is_entry_point` — analyst-owned flag (seeded by the
Ghidra adapter at first ingest for natural entry points such as `main`, never
overwritten on re-ingest; UI-toggleable via a future PATCH in I4) used to
drive `GET /binaries/{id}/entry-points` empty-canvas suggestions.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-21 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Plain (non-batch) ADD COLUMN: SQLite supports this natively without a
    # table rebuild for a simple nullable-with-default column addition.
    # Batch mode (table rebuild via a temp-table copy) is avoided here
    # because `functions` has a VIRTUAL GENERATED column
    # (`is_utility_effective`) that SQLite refuses to target in the
    # generated `INSERT INTO ... SELECT` copy step batch mode performs.
    op.add_column(
        "functions",
        sa.Column(
            "is_entry_point",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index("ix_functions_binary_entrypoint", "functions", ["binary_id", "is_entry_point"])


def downgrade() -> None:
    op.drop_index("ix_functions_binary_entrypoint", table_name="functions")
    op.drop_column("functions", "is_entry_point")
