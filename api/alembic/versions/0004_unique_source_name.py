"""unique source name

Revision ID: 0004_unique_source_name
Revises: 0003_nullable_source_hostname
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0004_unique_source_name"
down_revision = "0003_nullable_source_hostname"
branch_labels = None
depends_on = None


DEDUPE_SQL = """
WITH grouped AS (
    SELECT
        id,
        name,
        hostname,
        ip_address,
        port,
        FIRST_VALUE(id) OVER (PARTITION BY name ORDER BY created_at, id) AS canonical_id
    FROM sources
),
merged AS (
    SELECT
        canonical_id,
        (ARRAY_AGG(hostname)   FILTER (WHERE hostname   IS NOT NULL))[1] AS hostname,
        (ARRAY_AGG(ip_address) FILTER (WHERE ip_address IS NOT NULL))[1] AS ip_address,
        (ARRAY_AGG(port)       FILTER (WHERE port       IS NOT NULL))[1] AS port
    FROM grouped
    GROUP BY canonical_id
)
UPDATE sources s
SET
    hostname   = COALESCE(s.hostname,   m.hostname),
    ip_address = COALESCE(s.ip_address, m.ip_address),
    port       = COALESCE(s.port,       m.port)
FROM merged m
WHERE s.id = m.canonical_id;
"""

REASSIGN_LOGS_SQL = """
WITH ranked AS (
    SELECT
        id,
        FIRST_VALUE(id) OVER (PARTITION BY name ORDER BY created_at, id) AS canonical_id
    FROM sources
)
UPDATE logs SET source_id = ranked.canonical_id
FROM ranked
WHERE logs.source_id = ranked.id
  AND ranked.id <> ranked.canonical_id;
"""

REASSIGN_RULES_SQL = """
WITH ranked AS (
    SELECT
        id,
        FIRST_VALUE(id) OVER (PARTITION BY name ORDER BY created_at, id) AS canonical_id
    FROM sources
)
UPDATE alert_rules SET source_filter = ranked.canonical_id
FROM ranked
WHERE alert_rules.source_filter = ranked.id
  AND ranked.id <> ranked.canonical_id;
"""

DELETE_DUPLICATES_SQL = """
WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (PARTITION BY name ORDER BY created_at, id) AS rn
    FROM sources
)
DELETE FROM sources
USING ranked
WHERE sources.id = ranked.id AND ranked.rn > 1;
"""


def upgrade() -> None:
    op.execute(DEDUPE_SQL)
    op.execute(REASSIGN_LOGS_SQL)
    op.execute(REASSIGN_RULES_SQL)
    op.execute(DELETE_DUPLICATES_SQL)
    op.create_unique_constraint("uq_sources_name", "sources", ["name"])


def downgrade() -> None:
    op.drop_constraint("uq_sources_name", "sources", type_="unique")
