"""phase g polish

Revision ID: 0002_phase_g_polish
Revises: 0001_init
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_phase_g_polish"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("logs", sa.Column("idempotency_key", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_logs_idempotency_key", "logs", ["idempotency_key"])


def downgrade() -> None:
    op.drop_constraint("uq_logs_idempotency_key", "logs", type_="unique")
    op.drop_column("logs", "idempotency_key")
