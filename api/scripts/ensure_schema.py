from __future__ import annotations

import asyncio

from sqlalchemy import inspect, text

from llmh.db.session import engine

EXPECTED_TABLES = {"sources", "users", "logs", "alert_rules", "alert_events"}
BASE_REVISION = "0001_init"
POLISH_REVISION = "0002_phase_g_polish"


async def ensure_schema() -> None:
    async with engine.begin() as connection:
        def inspect_schema(sync_conn):
            inspection = inspect(sync_conn)
            table_names = set(inspection.get_table_names(schema="public"))
            log_columns: set[str] = set()
            if "logs" in table_names:
                log_columns = {column["name"] for column in inspection.get_columns("logs", schema="public")}
            return table_names, log_columns

        tables, log_columns = await connection.run_sync(inspect_schema)

        if "alembic_version" in tables:
            return

        app_tables = tables & EXPECTED_TABLES
        if not app_tables:
            return

        if app_tables != EXPECTED_TABLES:
            missing = ", ".join(sorted(EXPECTED_TABLES - app_tables))
            raise SystemExit(f"database has partial application schema; refusing to stamp head, missing: {missing}")

        revision = POLISH_REVISION if "idempotency_key" in log_columns else BASE_REVISION

        await connection.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        await connection.execute(text("DELETE FROM alembic_version"))
        await connection.execute(text("INSERT INTO alembic_version (version_num) VALUES (:version_num)"), {"version_num": revision})


def main() -> None:
    asyncio.run(ensure_schema())


if __name__ == "__main__":
    main()
