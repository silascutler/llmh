from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from llmh.db.models import Log, Source
from llmh.search.index import clear_index, search_logs
from llmh_worker.redis_consumer import (
    drain_retry_once,
    ensure_group,
    process_messages_once,
    reclaim_idle_once,
)


async def test_process_messages_once_ingests_and_acks(redis, worker_settings, session):
    await ensure_group(redis, worker_settings.stream, worker_settings.group)
    payload = {
        "source_key": {
            "hostname": "host-a",
            "ip_address": "10.0.0.5",
            "port": 22,
            "name": "laptop-a",
            "tags": ["dev"],
        },
        "tool": "codex",
        "level": "error",
        "message": "redis path",
        "raw": {},
        "tags": ["build"],
        "occurred_at": "2026-04-27T18:12:00Z",
    }
    await redis.xadd(worker_settings.stream, {"payload": json.dumps(payload)})

    processed = await process_messages_once(redis, worker_settings)
    assert processed == 1

    result = await session.execute(select(Log))
    rows = list(result.scalars())
    assert len(rows) == 1
    search = await search_logs(
        q="redis path",
        source_id=None,
        tool=None,
        level=None,
        tags=[],
        from_=None,
        to=None,
        session_id=None,
        limit=50,
        offset=0,
    )
    assert search["estimated_total"] == 1


async def test_reclaim_idle_once_processes_pending_message(redis, worker_settings, session):
    await ensure_group(redis, worker_settings.stream, worker_settings.group)
    payload = {
        "source_key": {
            "hostname": "host-b",
            "ip_address": "10.0.0.6",
            "port": 22,
            "name": "laptop-b",
            "tags": ["dev"],
        },
        "tool": "codex",
        "level": "warn",
        "message": "stuck pending",
        "raw": {},
        "tags": [],
        "occurred_at": "2026-04-27T18:13:00Z",
    }
    await redis.xadd(worker_settings.stream, {"payload": json.dumps(payload)})
    await redis.xreadgroup(
        groupname=worker_settings.group,
        consumername="other-consumer",
        streams={worker_settings.stream: ">"},
        count=1,
        block=1,
    )

    processed = await reclaim_idle_once(redis, worker_settings)
    assert processed == 1
    result = await session.execute(select(Log))
    rows = list(result.scalars())
    assert len(rows) == 1
    assert rows[0].message == "stuck pending"


async def test_drain_retry_once_reindexes_existing_logs(redis, worker_settings, session):
    source = Source(name="laptop", hostname="silas-laptop", tags=["dev"])
    session.add(source)
    await session.flush()
    log = Log(
        source=source,
        source_id=source.id,
        tool="claude-code",
        level="error",
        message="retry me",
        raw={},
        tags=["build"],
        occurred_at=datetime(2026, 4, 27, 18, 14, 0, tzinfo=timezone.utc),
    )
    session.add(log)
    await session.commit()
    result = await session.execute(select(Log).options(selectinload(Log.source)).where(Log.id == log.id))
    log = result.scalar_one()
    await clear_index()
    await redis.rpush("llmh:meili:retry", str(log.id))

    processed = await drain_retry_once(redis, worker_settings.retry_batch_size)
    assert processed == 1
    search = await search_logs(
        q="retry me",
        source_id=None,
        tool=None,
        level=None,
        tags=[],
        from_=None,
        to=None,
        session_id=None,
        limit=50,
        offset=0,
    )
    assert search["estimated_total"] == 1
