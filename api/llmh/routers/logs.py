from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from llmh.auth.deps import current_user
from llmh.db.models import Log, Source, User
from llmh.db.session import get_session
from llmh.schemas.log import LogOut, LogsPage, SessionSummary, SessionSummaryPage, decode_cursor, encode_cursor
from llmh.search.index import search_logs
from llmh.services.logs import fetch_logs_by_ids

router = APIRouter(prefix="/logs", tags=["logs"])

LogSortKey = Literal["level", "occurred_at", "source_name", "tool", "message", "tags"]
LogSortDirection = Literal["asc", "desc"]
SessionSortDirection = Literal["asc", "desc"]
LogActor = Literal["human", "assistant", "tool", "system", "other"]


def _actor_for_sender(sender: str | None) -> str:
    if sender == "user":
        return "human"
    if sender == "assistant":
        return "assistant"
    if sender == "tool_result":
        return "tool"
    if sender == "system":
        return "system"
    return "other"


def _sender_expr():
    return Log.raw["sender"].astext


def _apply_actor_filter(stmt, actors: list[LogActor]):
    if not actors:
        return stmt

    sender_expr = _sender_expr()
    clauses = []
    if "human" in actors:
        clauses.append(sender_expr == "user")
    if "assistant" in actors:
        clauses.append(sender_expr == "assistant")
    if "tool" in actors:
        clauses.append(sender_expr == "tool_result")
    if "system" in actors:
        clauses.append(sender_expr == "system")
    if "other" in actors:
        clauses.append(or_(sender_expr.is_(None), sender_expr.not_in(["user", "assistant", "tool_result", "system"])))
    return stmt.where(or_(*clauses)) if clauses else stmt


def _to_log_out(row: Log) -> LogOut:
    sender = row.raw.get("sender") if isinstance(row.raw, dict) else None
    return LogOut(
        id=row.id,
        source_id=row.source_id,
        source_name=row.source.name,
        tool=row.tool,
        actor=_actor_for_sender(sender),
        sender=sender,
        session_id=row.session_id,
        idempotency_key=row.idempotency_key,
        level=row.level,
        message=row.message,
        raw=row.raw,
        tags=row.tags,
        occurred_at=row.occurred_at,
        received_at=row.received_at,
    )


def _apply_log_filters(
    stmt,
    *,
    source_id: uuid.UUID | None,
    tool: str | None,
    level: str | None,
    actors: list[LogActor],
    tags: list[str],
    from_: datetime | None,
    to: datetime | None,
    session_id: str | None,
):
    if source_id is not None:
        stmt = stmt.where(Log.source_id == source_id)
    if tool is not None:
        stmt = stmt.where(Log.tool == tool)
    if level is not None:
        stmt = stmt.where(Log.level == level)
    stmt = _apply_actor_filter(stmt, actors)
    if from_ is not None:
        stmt = stmt.where(Log.occurred_at >= from_)
    if to is not None:
        stmt = stmt.where(Log.occurred_at <= to)
    if session_id is not None:
        stmt = stmt.where(Log.session_id == session_id)
    for tag in tags:
        stmt = stmt.where(Log.tags.any(tag))
    return stmt


def _apply_log_sort(stmt, *, sort_by: LogSortKey, sort_dir: LogSortDirection):
    direction = {
        "asc": lambda column: column.asc(),
        "desc": lambda column: column.desc(),
    }[sort_dir]
    if sort_by == "level":
        return stmt.order_by(direction(Log.level), Log.occurred_at.desc())
    if sort_by == "occurred_at":
        return stmt.order_by(direction(Log.occurred_at), Log.received_at.desc())
    if sort_by == "source_name":
        return stmt.order_by(direction(Source.name), Log.occurred_at.desc())
    if sort_by == "tool":
        return stmt.order_by(direction(Log.tool), Log.occurred_at.desc())
    if sort_by == "message":
        return stmt.order_by(direction(Log.message), Log.occurred_at.desc())
    return stmt.order_by(direction(func.array_to_string(Log.tags, ", ")), Log.occurred_at.desc())


def _normalize_query(q: str | None) -> str | None:
    if q is None:
        return None
    normalized = q.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
        normalized = normalized[1:-1].strip()
    return normalized or None


@router.get("/sessions", response_model=SessionSummaryPage)
async def list_sessions(
    q: str | None = None,
    source_id: uuid.UUID | None = None,
    tool: str | None = None,
    actor: list[LogActor] | None = Query(default=None),
    sort_dir: SessionSortDirection = Query(default="desc"),
    limit: int = Query(default=100, ge=1, le=300),
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> SessionSummaryPage:
    filtered = select(
        Log.session_id.label("session_id"),
        Log.source_id.label("source_id"),
        Log.tool.label("tool"),
        Log.message.label("message"),
        Log.occurred_at.label("occurred_at"),
        func.row_number()
        .over(partition_by=(Log.source_id, Log.session_id), order_by=(Log.occurred_at.desc(), Log.received_at.desc()))
        .label("row_number"),
        func.count().over(partition_by=(Log.source_id, Log.session_id)).label("log_count"),
    ).where(Log.session_id.is_not(None))
    normalized_q = _normalize_query(q)
    if normalized_q:
        pattern = f"%{normalized_q}%"
        filtered = filtered.join(Source, Source.id == Log.source_id).where(
            or_(
                Log.message.ilike(pattern),
                cast(Log.raw, Text).ilike(pattern),
                Log.tool.ilike(pattern),
                Source.name.ilike(pattern),
            )
        )
    if source_id is not None:
        filtered = filtered.where(Log.source_id == source_id)
    if tool is not None:
        filtered = filtered.where(Log.tool == tool)
    actor_values = actor or []
    filtered = _apply_actor_filter(filtered, actor_values)

    filtered_subquery = filtered.subquery()
    session_order = filtered_subquery.c.occurred_at.asc() if sort_dir == "asc" else filtered_subquery.c.occurred_at.desc()
    stmt = (
        select(
            filtered_subquery.c.session_id,
            filtered_subquery.c.tool,
            filtered_subquery.c.log_count,
            filtered_subquery.c.occurred_at,
            filtered_subquery.c.message,
            Source.name.label("source_name"),
        )
        .join(Source, Source.id == filtered_subquery.c.source_id)
        .where(filtered_subquery.c.row_number == 1)
        .order_by(session_order, Source.name.asc(), filtered_subquery.c.session_id.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()

    items = [
        SessionSummary(
            session_id=row[0],
            tool=row[1],
            log_count=row[2],
            latest_occurred_at=row[3],
            preview=row[4],
            source_name=row[5],
        )
        for row in rows
    ]
    return SessionSummaryPage(items=items)


@router.get("", response_model=LogsPage)
async def list_logs(
    q: str | None = None,
    source_id: uuid.UUID | None = None,
    tool: str | None = None,
    level: str | None = Query(default=None, pattern="^(debug|info|warn|error)$"),
    actor: list[LogActor] | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    session_id: str | None = None,
    sort_by: LogSortKey = Query(default="occurred_at"),
    sort_dir: LogSortDirection = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> LogsPage:
    try:
        offset = decode_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    normalized_q = _normalize_query(q)
    tag_values = tags or []
    actor_values = actor or []
    has_filters = any([normalized_q, source_id, tool, level, actor_values, tag_values, from_, to, session_id])
    if not has_filters:
        count_stmt = select(func.count()).select_from(Log)
        estimated_total = int((await session.execute(count_stmt)).scalar_one())
        stmt = select(Log).options(selectinload(Log.source)).join(Source)
        stmt = _apply_log_sort(stmt, sort_by=sort_by, sort_dir=sort_dir).limit(limit + 1).offset(offset)
        result = await session.execute(stmt)
        rows = list(result.scalars())
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = encode_cursor(offset + limit) if has_more else None
        return LogsPage(items=[_to_log_out(row) for row in items], next_cursor=next_cursor, estimated_total=estimated_total)

    if not normalized_q:
        filtered_stmt = select(Log.id).join(Source)
        filtered_stmt = _apply_log_filters(
            filtered_stmt,
            source_id=source_id,
            tool=tool,
            level=level,
            actors=actor_values,
            tags=tag_values,
            from_=from_,
            to=to,
            session_id=session_id,
        )
        count_stmt = select(func.count()).select_from(filtered_stmt.subquery())
        estimated_total = int((await session.execute(count_stmt)).scalar_one())
        stmt = select(Log).options(selectinload(Log.source)).join(Source)
        stmt = _apply_log_filters(
            stmt,
            source_id=source_id,
            tool=tool,
            level=level,
            actors=actor_values,
            tags=tag_values,
            from_=from_,
            to=to,
            session_id=session_id,
        )
        stmt = _apply_log_sort(stmt, sort_by=sort_by, sort_dir=sort_dir)
        stmt = stmt.limit(limit + 1).offset(offset)
        result = await session.execute(stmt)
        rows = list(result.scalars())
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = encode_cursor(offset + limit) if has_more else None
        return LogsPage(items=[_to_log_out(row) for row in items], next_cursor=next_cursor, estimated_total=estimated_total)

    search_result = await search_logs(
        q=normalized_q or "",
        source_id=source_id,
        tool=tool,
        level=level,
        actors=actor_values,
        tags=tag_values,
        from_=from_,
        to=to,
        session_id=session_id,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    if not search_result["ids"]:
        stmt = select(Log).options(selectinload(Log.source)).join(Source)
        stmt = _apply_log_filters(
            stmt,
            source_id=source_id,
            tool=tool,
            level=level,
            actors=actor_values,
            tags=tag_values,
            from_=from_,
            to=to,
            session_id=session_id,
        )
        pattern = f"%{normalized_q}%"
        stmt = stmt.where(
            or_(
                Log.message.ilike(pattern),
                cast(Log.raw, Text).ilike(pattern),
            )
        )
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        estimated_total = int((await session.execute(count_stmt)).scalar_one())
        stmt = _apply_log_sort(stmt, sort_by=sort_by, sort_dir=sort_dir).limit(limit + 1).offset(offset)
        result = await session.execute(stmt)
        rows = list(result.scalars())
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = encode_cursor(offset + limit) if has_more else None
        return LogsPage(
            items=[_to_log_out(row) for row in items],
            next_cursor=next_cursor,
            estimated_total=estimated_total,
        )
    log_ids = [uuid.UUID(item) for item in search_result["ids"]]
    rows = await fetch_logs_by_ids(session, log_ids)
    next_cursor = encode_cursor(offset + limit) if search_result["has_more"] else None
    return LogsPage(
        items=[_to_log_out(row) for row in rows],
        next_cursor=next_cursor,
        estimated_total=search_result["estimated_total"],
    )
