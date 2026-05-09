from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from llmh.db.models import AlertRule
from llmh.rule_notifications import notify_rules_changed
from llmh.schemas.rule import RuleCreate, RuleUpdate


async def list_rules(session: AsyncSession) -> list[AlertRule]:
    result = await session.execute(select(AlertRule).order_by(AlertRule.created_at.desc()))
    return list(result.scalars())


async def get_rule(session: AsyncSession, rule_id: uuid.UUID) -> AlertRule | None:
    result = await session.execute(select(AlertRule).where(AlertRule.id == rule_id))
    return result.scalar_one_or_none()


async def create_rule(session: AsyncSession, payload: RuleCreate, created_by: uuid.UUID) -> AlertRule:
    rule = AlertRule(created_by=created_by, **payload.model_dump())
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    await notify_rules_changed()
    return rule


async def update_rule(session: AsyncSession, rule: AlertRule, payload: RuleUpdate) -> AlertRule:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    await session.commit()
    await session.refresh(rule)
    await notify_rules_changed()
    return rule


async def delete_rule(session: AsyncSession, rule: AlertRule) -> None:
    await session.delete(rule)
    await session.commit()
    await notify_rules_changed()
