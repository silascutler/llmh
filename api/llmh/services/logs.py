from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Sequence

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from llmh.config import get_settings
from llmh.alerts.evaluator import evaluate_for
from llmh.db.models import Log, Source
from llmh.metrics import metrics
from llmh.schemas.log import LogIngest

MEILI_RETRY_LIST = "llmh:meili:retry"
logger = logging.getLogger(__name__)


async def _redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


async def _resolve_source(session: AsyncSession, payload: LogIngest) -> Source:
    if payload.source_id is not None:
        result = await session.execute(select(Source).where(Source.id == payload.source_id))
        source = result.scalar_one_or_none()
        if source is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown source_id: {payload.source_id}")
        return source

    assert payload.source_key is not None
    key = payload.source_key

    result = await session.execute(select(Source).where(Source.name == key.name))
    source = result.scalar_one_or_none()
    if source is not None:
        changed = False
        if source.hostname is None and key.hostname is not None:
            source.hostname = key.hostname
            changed = True
        if source.ip_address is None and key.ip_address is not None:
            source.ip_address = key.ip_address
            changed = True
        if source.port is None and key.port is not None:
            source.port = key.port
            changed = True
        if changed:
            await session.flush()
        return source

    source = Source(
        name=key.name,
        hostname=key.hostname,
        ip_address=key.ip_address,
        port=key.port,
        tags=key.tags,
    )
    try:
        async with session.begin_nested():
            session.add(source)
            await session.flush()
    except IntegrityError:
        result = await session.execute(select(Source).where(Source.name == key.name))
        source = result.scalar_one()
    return source


def _validate_payload_size(payload: LogIngest) -> None:
    raw_size = len(json.dumps(payload.raw, separators=(",", ":")).encode("utf-8"))
    if raw_size > get_settings().raw_payload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"raw payload too large: {raw_size} bytes",
        )


async def ingest(session: AsyncSession, payloads: Sequence[LogIngest], *, evaluate_alerts: bool = True) -> list[Log]:
    rows: list[Log] = []
    seen_idempotency: dict[str, Log] = {}
    for payload in payloads:
        if payload.idempotency_key:
            existing = seen_idempotency.get(payload.idempotency_key)
            if existing is None:
                result = await session.execute(
                    select(Log).options(selectinload(Log.source)).where(Log.idempotency_key == payload.idempotency_key),
                )
                existing = result.scalar_one_or_none()
                if existing is not None:
                    seen_idempotency[payload.idempotency_key] = existing
            if existing is not None:
                rows.append(existing)
                metrics.inc("logs_deduplicated_total")
                continue

        _validate_payload_size(payload)
        source = await _resolve_source(session, payload)
        row = Log(
            source=source,
            source_id=source.id,
            tool=payload.tool,
            session_id=payload.session_id,
            idempotency_key=payload.idempotency_key,
            level=payload.level,
            message=payload.message,
            raw=payload.raw,
            tags=payload.tags,
            occurred_at=payload.occurred_at,
        )
        session.add(row)
        rows.append(row)
        if payload.idempotency_key:
            seen_idempotency[payload.idempotency_key] = row

    await session.flush()
    await session.commit()

    for row in rows:
        await session.refresh(row, attribute_names=["source"])

    metrics.inc("logs_ingested_total", value=len(rows))

    if rows:
        redis = await _redis_client()
        try:
            await redis.rpush(MEILI_RETRY_LIST, *[str(row.id) for row in rows])
        finally:
            await redis.aclose()

    if evaluate_alerts:
        await evaluate_for(rows, session)

    return rows


async def fetch_logs_by_ids(session: AsyncSession, log_ids: Sequence[uuid.UUID]) -> list[Log]:
    if not log_ids:
        return []
    normalized_ids = [log_id if isinstance(log_id, uuid.UUID) else uuid.UUID(str(log_id)) for log_id in log_ids]
    stmt = select(Log).options(selectinload(Log.source)).where(Log.id.in_(normalized_ids))
    result = await session.execute(stmt)
    rows = list(result.scalars())
    order = {log_id: index for index, log_id in enumerate(normalized_ids)}
    rows.sort(key=lambda row: order[row.id])
    return rows
