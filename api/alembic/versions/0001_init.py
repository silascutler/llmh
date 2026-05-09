"""initial schema

Revision ID: 0001_init
Revises:
Create Date: 2026-04-27 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("hostname", sa.Text(), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("hostname", "ip_address", "port", name="uq_sources_host_ip_port"),
    )
    op.create_index("ix_sources_name", "sources", ["name"], unique=False)
    op.create_index("ix_sources_tags", "sources", ["tags"], unique=False, postgresql_using="gin")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("role IN ('admin','viewer')", name="ck_users_role"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )

    op.create_table(
        "logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("level IN ('debug','info','warn','error')", name="ck_logs_level"),
    )
    op.create_index("ix_logs_source_occurred_at", "logs", ["source_id", "occurred_at"], unique=False)
    op.create_index("ix_logs_tool", "logs", ["tool"], unique=False)
    op.create_index("ix_logs_occurred_at", "logs", ["occurred_at"], unique=False)
    op.create_index("ix_logs_tags", "logs", ["tags"], unique=False, postgresql_using="gin")

    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("match_type", sa.Text(), nullable=False),
        sa.Column("match_value", sa.Text(), nullable=False),
        sa.Column("source_filter", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tag_filter", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("email_to", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("match_type IN ('keyword','regex','source','tag')", name="ck_alert_rules_match_type"),
    )
    op.create_index("ix_alert_rules_enabled", "alert_rules", ["enabled"], unique=False)

    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("log_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("logs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("delivery_status", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_alert_events_rule_fired_at", "alert_events", ["rule_id", "fired_at"], unique=False)
    op.create_index("ix_alert_events_log_id", "alert_events", ["log_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_alert_events_log_id", table_name="alert_events")
    op.drop_index("ix_alert_events_rule_fired_at", table_name="alert_events")
    op.drop_table("alert_events")
    op.drop_index("ix_alert_rules_enabled", table_name="alert_rules")
    op.drop_table("alert_rules")
    op.drop_index("ix_logs_tags", table_name="logs")
    op.drop_index("ix_logs_occurred_at", table_name="logs")
    op.drop_index("ix_logs_tool", table_name="logs")
    op.drop_index("ix_logs_source_occurred_at", table_name="logs")
    op.drop_table("logs")
    op.drop_table("users")
    op.drop_index("ix_sources_tags", table_name="sources")
    op.drop_index("ix_sources_name", table_name="sources")
    op.drop_table("sources")

