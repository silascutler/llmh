from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

TEST_DATABASE_URL = "postgresql+asyncpg://llmh:changeme@postgres:5432/llmh_api_test"
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

from llmh.auth.passwords import hash_password  # noqa: E402
from llmh.alerts.evaluator import clear_rule_cache  # noqa: E402
from llmh.db.base import Base  # noqa: E402
from llmh.db.models import AlertEvent, AlertRule, Log, Source, User  # noqa: E402
from llmh.db.session import AsyncSessionLocal, engine  # noqa: E402
from llmh.main import app  # noqa: E402
from llmh.metrics import metrics  # noqa: E402
from llmh.search.index import clear_index, ensure_index  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def migrated_db() -> AsyncIterator[None]:
    admin_engine = create_async_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    async with admin_engine.begin() as connection:
        exists = await connection.execute(text("SELECT 1 FROM pg_database WHERE datname = 'llmh_api_test'"))
        if exists.scalar_one_or_none() is None:
            await connection.execute(text("CREATE DATABASE llmh_api_test"))
    await admin_engine.dispose()

    async with engine.begin() as connection:
        await connection.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
        await connection.execute(text('CREATE EXTENSION IF NOT EXISTS "citext"'))
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("ALTER TABLE sources ALTER COLUMN hostname DROP NOT NULL"))
        await connection.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        await connection.execute(text("DELETE FROM alembic_version"))
        await connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0004_unique_source_name')"))
    await ensure_index()
    yield


@pytest.fixture(autouse=True)
async def clean_db() -> AsyncIterator[None]:
    async with AsyncSessionLocal() as session:
        for model in (AlertEvent, AlertRule, Log, User, Source):
            await session.execute(delete(model))
        await session.commit()
    clear_rule_cache()
    await clear_index()
    await _clear_rate_limits()
    metrics.reset()
    yield
    async with AsyncSessionLocal() as session:
        for model in (AlertEvent, AlertRule, Log, User, Source):
            await session.execute(delete(model))
        await session.commit()
    clear_rule_cache()
    await clear_index()
    await _clear_rate_limits()
    metrics.reset()


async def _clear_rate_limits() -> None:
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    try:
        keys = [key async for key in redis.scan_iter("llmh:rate-limit:*")]
        if keys:
            await redis.delete(*keys)
    finally:
        await redis.aclose()


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await client.delete("llmh:meili:retry")
    try:
        yield client
    finally:
        await client.delete("llmh:meili:retry")
        await client.aclose()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as db_session:
        yield db_session


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest.fixture
async def admin_user(session: AsyncSession) -> User:
    user = User(username="admin", password_hash=hash_password("secret"), role="admin")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def viewer_user(session: AsyncSession) -> User:
    user = User(username="viewer", password_hash=hash_password("secret"), role="viewer")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def logged_in_admin(client: AsyncClient, admin_user: User) -> AsyncClient:
    response = await client.post("/auth/login", json={"username": admin_user.username, "password": "secret"})
    assert response.status_code == 200
    return client


@pytest.fixture
async def logged_in_viewer(client: AsyncClient, viewer_user: User) -> AsyncClient:
    response = await client.post("/auth/login", json={"username": viewer_user.username, "password": "secret"})
    assert response.status_code == 200
    return client
