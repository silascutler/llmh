"""allow nullable source hostname

Revision ID: 0003_nullable_source_hostname
Revises: 0002_phase_g_polish
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_nullable_source_hostname"
down_revision = "0002_phase_g_polish"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("sources", "hostname", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE sources SET hostname = name WHERE hostname IS NULL")
    op.alter_column("sources", "hostname", existing_type=sa.Text(), nullable=False)
