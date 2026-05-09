from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from llmh.auth.rate_limit import enforce_rate_limit
from llmh.auth.ingest_token import require_ingest_token
from llmh.config import get_settings
from llmh.db.session import get_session
from llmh.schemas.log import IngestResponse, LogIngestBatch
from llmh.services.logs import ingest as ingest_logs

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=IngestResponse, dependencies=[Depends(require_ingest_token)])
async def ingest(body: LogIngestBatch, request: Request, session: AsyncSession = Depends(get_session)) -> IngestResponse:
    settings = get_settings()
    await enforce_rate_limit(request, bucket="ingest", limit=settings.ingest_rate_limit_per_minute, window_seconds=60)
    if len(body.logs) > settings.ingest_batch_max:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ingest batch too large")
    rows = await ingest_logs(session, body.logs)
    return IngestResponse(ids=[row.id for row in rows])
