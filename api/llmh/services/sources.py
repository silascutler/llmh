from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from llmh.db.models import Log, Source
from llmh.search.index import delete_logs as delete_index_logs
from llmh.schemas.source import SourceCreate, SourceUpdate


async def list_sources(session: AsyncSession, q: str | None, tag: str | None, limit: int, offset: int) -> list[Source]:
    stmt = (
        select(
            Source,
            func.count(Log.id).label("log_count"),
            func.count(func.distinct(Log.session_id)).label("session_count"),
        )
        .outerjoin(Log, Log.source_id == Source.id)
        .group_by(Source.id)
        .order_by(Source.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    filters = []
    if q:
        needle = f"%{q.lower()}%"
        filters.append(
            or_(
                func.lower(Source.name).like(needle),
                func.lower(Source.hostname).like(needle),
                func.lower(func.coalesce(Source.notes, "")).like(needle),
            )
        )
    if tag:
        filters.append(Source.tags.any(tag))
    if filters:
        stmt = stmt.where(and_(*filters))
    result = await session.execute(stmt)
    rows = []
    for source, log_count, session_count in result.all():
        setattr(source, "log_count", int(log_count or 0))
        setattr(source, "session_count", int(session_count or 0))
        rows.append(source)
    return rows


async def create_source(session: AsyncSession, payload: SourceCreate) -> Source:
    data = payload.model_dump()
    hostname = data.get("hostname") or data["name"]
    data["hostname"] = hostname
    source = Source(**data)
    session.add(source)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise
    await session.refresh(source)
    return source


async def get_source(session: AsyncSession, source_id: uuid.UUID) -> Source | None:
    result = await session.execute(select(Source).where(Source.id == source_id))
    return result.scalar_one_or_none()


async def get_source_detail(session: AsyncSession, source_id: uuid.UUID) -> tuple[Source | None, datetime | None]:
    stmt = (
        select(
            Source,
            func.max(Log.occurred_at),
            func.count(Log.id),
            func.count(func.distinct(Log.session_id)),
        )
        .outerjoin(Log, Log.source_id == Source.id)
        .where(Source.id == source_id)
        .group_by(Source.id)
    )
    result = await session.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None, None
    source = row[0]
    setattr(source, "log_count", int(row[2] or 0))
    setattr(source, "session_count", int(row[3] or 0))
    return source, row[1]


async def update_source(session: AsyncSession, source: Source, payload: SourceUpdate) -> Source:
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(source, key, value)
    source.updated_at = datetime.now(timezone.utc)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise
    await session.refresh(source)
    return source


async def delete_source(session: AsyncSession, source: Source) -> None:
    result = await session.execute(select(Log.id).where(Log.source_id == source.id))
    log_ids = [str(row[0]) for row in result.all()]
    await session.delete(source)
    await session.commit()
    await delete_index_logs(log_ids)


async def list_source_logs(session: AsyncSession, source_id: uuid.UUID) -> list[Log]:
    stmt = (
        select(Log)
        .where(Log.source_id == source_id)
        .order_by(Log.occurred_at.asc(), Log.received_at.asc(), Log.id.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars())


async def export_source_archive(session: AsyncSession, source_id: uuid.UUID) -> bytes | None:
    source, last_seen_at = await get_source_detail(session, source_id)
    if source is None:
        return None
    logs = await list_source_logs(session, source_id)
    stats = await source_stats(session, source_id)

    export_payload = {
        "source": {
            "id": str(source.id),
            "name": source.name,
            "hostname": source.hostname,
            "ip_address": str(source.ip_address) if source.ip_address is not None else None,
            "port": source.port,
            "notes": source.notes,
            "tags": source.tags,
            "created_at": source.created_at.isoformat(),
            "updated_at": source.updated_at.isoformat(),
            "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
        },
        "stats": stats,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "log_count": len(logs),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("source.json", json.dumps(export_payload, indent=2, sort_keys=True))
        log_lines = []
        for row in logs:
            log_lines.append(
                json.dumps(
                    {
                        "id": str(row.id),
                        "source_id": str(row.source_id),
                        "tool": row.tool,
                        "session_id": row.session_id,
                        "idempotency_key": row.idempotency_key,
                        "level": row.level,
                        "message": row.message,
                        "raw": row.raw,
                        "tags": row.tags,
                        "occurred_at": row.occurred_at.isoformat(),
                        "received_at": row.received_at.isoformat(),
                    },
                    sort_keys=True,
                )
            )
        archive.writestr("logs.jsonl", "\n".join(log_lines) + ("\n" if log_lines else ""))
    return buffer.getvalue()


async def source_stats(session: AsyncSession, source_id: uuid.UUID) -> dict[str, int]:
    stmt = (
        select(Log.level, func.count(Log.id))
        .where(Log.source_id == source_id)
        .group_by(Log.level)
    )
    result = await session.execute(stmt)
    stats = {"debug": 0, "info": 0, "warn": 0, "error": 0}
    for level, count in result.all():
        stats[level] = count
    return stats
