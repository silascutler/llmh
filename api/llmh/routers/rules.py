from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from llmh.alerts.evaluator import clear_rule_cache
from llmh.auth.deps import current_user, require_admin
from llmh.db.models import User
from llmh.db.session import get_session
from llmh.schemas.rule import RuleCreate, RuleOut, RuleUpdate
from llmh.services import rules as rules_service

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("", response_model=list[RuleOut])
async def list_rules(
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[RuleOut]:
    rows = await rules_service.list_rules(session)
    return [RuleOut.model_validate(row) for row in rows]


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleCreate,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> RuleOut:
    row = await rules_service.create_rule(session, body, user.id)
    clear_rule_cache()
    return RuleOut.model_validate(row)


@router.get("/{rule_id}", response_model=RuleOut)
async def get_rule(
    rule_id: uuid.UUID,
    _: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> RuleOut:
    row = await rules_service.get_rule(session, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="rule not found")
    return RuleOut.model_validate(row)


@router.patch("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> RuleOut:
    row = await rules_service.get_rule(session, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="rule not found")
    updated = await rules_service.update_rule(session, row, body)
    clear_rule_cache()
    return RuleOut.model_validate(updated)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: uuid.UUID,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    row = await rules_service.get_rule(session, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail="rule not found")
    await rules_service.delete_rule(session, row)
    clear_rule_cache()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
