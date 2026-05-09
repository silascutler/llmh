from __future__ import annotations

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from llmh.auth.deps import current_user, require_admin
from llmh.db.models import User
from llmh.db.session import get_session
from llmh.schemas.source import SourceCreate, SourceDetail, SourceOut, SourceStats, SourceUpdate
from llmh.services import sources as source_service

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
async def list_sources(
    q: str | None = None,
    tag: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SourceOut]:
    rows = await source_service.list_sources(session, q=q, tag=tag, limit=limit, offset=offset)
    return [SourceOut.model_validate(row) for row in rows]


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: SourceCreate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SourceOut:
    try:
        row = await source_service.create_source(session, body)
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="source already exists") from exc
    return SourceOut.model_validate(row)


@router.get("/{source_id}", response_model=SourceDetail)
async def get_source(
    source_id: uuid.UUID,
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> SourceDetail:
    source, last_seen_at = await source_service.get_source_detail(session, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    payload = SourceDetail.model_validate(source)
    payload.last_seen_at = last_seen_at
    return payload


@router.patch("/{source_id}", response_model=SourceOut)
async def update_source(
    source_id: uuid.UUID,
    body: SourceUpdate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SourceOut:
    source = await source_service.get_source(session, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    try:
        updated = await source_service.update_source(session, source, body)
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="source already exists") from exc
    return SourceOut.model_validate(updated)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    source = await source_service.get_source(session, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    await source_service.delete_source(session, source)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{source_id}/export")
async def export_source(
    source_id: uuid.UUID,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    archive_bytes = await source_service.export_source_archive(session, source_id)
    if archive_bytes is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    source = await source_service.get_source(session, source_id)
    assert source is not None
    filename = quote(f"{source.name or source.hostname}-{source_id}.zip")
    return StreamingResponse(
        iter([archive_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{source_id}/stats", response_model=SourceStats)
async def get_source_stats(
    source_id: uuid.UUID,
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> SourceStats:
    source = await source_service.get_source(session, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    stats = await source_service.source_stats(session, source_id)
    return SourceStats(**stats)
