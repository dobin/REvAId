"""add_llm_worker_status

Persist the last meaningful provider-backed summarization outcome for every
adapter/model pair. This supports a passive sidebar status without issuing a
completion request every time the UI refreshes.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-05 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_worker_statuses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("adapter", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("observed_at", sa.String(), nullable=False),
        sa.Column("function_id", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.CheckConstraint(
            "outcome IN ('success', 'failure', 'rate_limited')",
            name=op.f("ck_llm_worker_statuses_outcome_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_worker_statuses")),
        sa.UniqueConstraint(
            "adapter", "model", name="ux_llm_worker_statuses_adapter_model"
        ),
    )
    op.create_index(
        "ix_llm_worker_statuses_adapter_model",
        "llm_worker_statuses",
        ["adapter", "model"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_llm_worker_statuses_adapter_model", table_name="llm_worker_statuses")
    op.drop_table("llm_worker_statuses")