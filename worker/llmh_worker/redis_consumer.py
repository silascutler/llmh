from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from redis.asyncio import Redis

from llmh.config import get_settings
from llmh.db.session import AsyncSessionLocal
from llmh.schemas.log import LogIngest
from llmh.search.index import index_logs
from llmh.services.logs import MEILI_RETRY_LIST, fetch_logs_by_ids, ingest

logger = logging.getLogger(__name__)


@dataclass
class WorkerSettings:
    stream: str
    group: str
    consumer: str
    read_count: int = 64
    read_block_ms: int = 5000
    reclaim_idle_ms: int = 60000
    retry_batch_size: int = 100


def load_worker_settings() -> WorkerSettings:
    settings = get_settings()
    hostname = os.getenv("HOSTNAME", "worker")
    consumer = f"{hostname}-{os.getpid()}"
    return WorkerSettings(
        stream=settings.redis_ingest_stream,
        group=settings.redis_consumer_group,
        consumer=consumer,
    )


async def redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


async def ensure_group(redis: Redis, stream: str, group: str) -> None:
    try:
        await redis.xgroup_create(stream, group, id="0", mkstream=True)
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def _parse_payload(raw_payload: str) -> LogIngest:
    return LogIngest.model_validate(json.loads(raw_payload))


async def _process_single_message(redis: Redis, worker: WorkerSettings, msg_id: str, fields: dict[str, str]) -> bool:
    payload_raw = fields.get("payload")
    if payload_raw is None:
        logger.error("missing payload field for stream message %s", msg_id)
        return False
    try:
        payload = _parse_payload(payload_raw)
        async with AsyncSessionLocal() as session:
            await ingest(session, [payload])
        await redis.xack(worker.stream, worker.group, msg_id)
        return True
    except Exception:
        logger.exception("ingest failed for %s", msg_id)
        return False


def _flatten_stream_response(messages) -> list[tuple[str, dict[str, str]]]:
    flattened: list[tuple[str, dict[str, str]]] = []
    for _, entries in messages:
        for msg_id, fields in entries:
            flattened.append((msg_id, fields))
    return flattened


async def process_messages_once(redis: Redis, worker: WorkerSettings) -> int:
    messages = await redis.xreadgroup(
        groupname=worker.group,
        consumername=worker.consumer,
        streams={worker.stream: ">"},
        count=worker.read_count,
        block=worker.read_block_ms,
    )
    processed = 0
    for msg_id, fields in _flatten_stream_response(messages):
        if await _process_single_message(redis, worker, msg_id, fields):
            processed += 1
    return processed


async def reclaim_idle_once(redis: Redis, worker: WorkerSettings) -> int:
    result = await redis.xautoclaim(
        name=worker.stream,
        groupname=worker.group,
        consumername=worker.consumer,
        min_idle_time=worker.reclaim_idle_ms,
        start_id="0-0",
        count=worker.read_count,
    )
    claimed_messages = result[1] if len(result) > 1 else []
    processed = 0
    for msg_id, fields in claimed_messages:
        if await _process_single_message(redis, worker, msg_id, fields):
            processed += 1
    return processed


async def drain_retry_once(redis: Redis, batch_size: int | None = None) -> int:
    size = batch_size or load_worker_settings().retry_batch_size
    processed = 0
    async with AsyncSessionLocal() as session:
        for _ in range(size):
            log_id = await redis.lpop(MEILI_RETRY_LIST)
            if not log_id:
                break
            rows = await fetch_logs_by_ids(session, [log_id])
            if not rows:
                continue
            await index_logs(rows)
            processed += 1
    return processed


async def run_forever() -> None:
    logging.basicConfig(level=get_settings().log_level)
    worker = load_worker_settings()
    redis = await redis_client()
    try:
        await ensure_group(redis, worker.stream, worker.group)
        while True:
            await process_messages_once(redis, worker)
            await reclaim_idle_once(redis, worker)
            await drain_retry_once(redis, worker.retry_batch_size)
    finally:
        await redis.aclose()
