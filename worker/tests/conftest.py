from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from redis.asyncio import Redis
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = "postgresql+asyncpg://llmh:changeme@postgres:5432/llmh_worker_test"
ADMIN_DATABASE_URL = "postgresql+asyncpg://llmh:changeme@postgres:5432/postgres"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DATABASE_DISABLE_POOL"] = "true"
os.environ["REDIS_URL"] = "redis://redis:6379/0"
os.environ["REDIS_INGEST_STREAM"] = "llmh:ingest"
os.environ["REDIS_CONSUMER_GROUP"] = "llmh-workers"
os.environ["MEILI_URL"] = "http://meilisearch:7700"
os.environ["MEILI_MASTER_KEY"] = "changeme-please-32-chars-min-aaaaa"
os.environ["INGEST_BEARER_TOKEN"] = "test-ingest-token"
os.environ["SESSION_SECRET"] = "test-session-secret-test-session-secret"
os.environ["CORS_ORIGINS"] = '["http://localhost:3000"]'

from llmh.db.base import Base  # noqa: E402
from llmh.db.models import AlertEvent, AlertRule, Log, Source, User  # noqa: E402
from llmh.db.session import AsyncSessionLocal, engine  # noqa: E402
from llmh.search.index import clear_index, ensure_index  # noqa: E402
from llmh_worker.redis_consumer import WorkerSettings, redis_client  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def migrated_db() -> AsyncIterator[None]:
    admin_engine = create_async_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.begin() as connection:
        exists = await connection.execute(text("SELECT 1 FROM pg_database WHERE datname = 'llmh_worker_test'"))
        if exists.scalar_one_or_none() is None:
            await connection.execute(text("CREATE DATABASE llmh_worker_test"))
    await admin_engine.dispose()

    async with engine.begin() as connection:
        await connection.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        await connection.execute(text('CREATE EXTENSION IF NOT EXISTS "citext"'))
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        await connection.execute(text("DELETE FROM alembic_version"))
        await connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0002_phase_g_polish')"))
    await ensure_index()
    yield


@pytest.fixture(autouse=True)
async def clean_state() -> AsyncIterator[None]:
    async with AsyncSessionLocal() as session:
        for model in (AlertEvent, AlertRule, Log, User, Source):
            await session.execute(delete(model))
        await session.commit()
    redis = await redis_client()
    await redis.delete("llmh:ingest", "llmh:meili:retry")
    try:
        await redis.xgroup_destroy("llmh:ingest", "llmh-workers")
    except Exception:
        pass
    await clear_index()
    await redis.aclose()
    yield


@pytest.fixture
async def session() -> AsyncIterator:
    async with AsyncSessionLocal() as db_session:
        yield db_session


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    client = await redis_client()
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def worker_settings() -> WorkerSettings:
    return WorkerSettings(
        stream="llmh:ingest",
        group="llmh-workers",
        consumer="test-consumer",
        read_count=16,
        read_block_ms=1,
        reclaim_idle_ms=0,
        retry_batch_size=16,
    )
