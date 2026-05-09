from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from llmh.alerts.evaluator import list_alert_events
from llmh.auth.deps import current_user
from llmh.db.models import User
from llmh.db.session import get_session
from llmh.schemas.alert import AlertEventOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertEventOut])
async def get_alerts(
    rule_id: uuid.UUID | None = None,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AlertEventOut]:
    rows = await list_alert_events(session, rule_id=rule_id, from_=from_, to=to, limit=limit, offset=offset)
    return [
        AlertEventOut(
            id=event.id,
            rule_id=rule.id,
            rule_name=rule.name,
            log_id=log.id,
            log_message=log.message,
            source_name=log.source.name,
            occurred_at=log.occurred_at,
            fired_at=event.fired_at,
            delivery_status=event.delivery_status,
        )
        for event, rule, log in rows
    ]
