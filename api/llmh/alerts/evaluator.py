from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from llmh.alerts.email import send_email
from llmh.alerts.webhook import send_webhook
from llmh.db.models import AlertEvent, AlertRule, Log
from llmh.metrics import metrics


@dataclass
class RulesCache:
    ttl_seconds: int = 30
    _loaded_at: float = 0.0
    _rules: list[AlertRule] = field(default_factory=list)

    def valid(self) -> bool:
        return bool(self._rules) and (time.time() - self._loaded_at) < self.ttl_seconds

    def set(self, rules: list[AlertRule]) -> None:
        self._rules = rules
        self._loaded_at = time.time()

    def clear(self) -> None:
        self._rules = []
        self._loaded_at = 0.0


rules_cache = RulesCache()
_regex_cache: dict[str, re.Pattern[str]] = {}


def clear_rule_cache() -> None:
    rules_cache.clear()
    _regex_cache.clear()
    metrics.inc("rule_cache_invalidations_total")


def match(rule: AlertRule, log: Log) -> bool:
    if rule.source_filter and log.source_id != rule.source_filter:
        return False
    if rule.tag_filter and not set(log.tags).intersection(rule.tag_filter):
        return False

    if rule.match_type == "keyword":
        return rule.match_value.lower() in log.message.lower()
    if rule.match_type == "regex":
        pattern = _regex_cache.setdefault(rule.match_value, re.compile(rule.match_value))
        return bool(pattern.search(log.message))
    if rule.match_type == "source":
        return rule.source_filter is not None and log.source_id == rule.source_filter
    if rule.match_type == "tag":
        return bool(rule.tag_filter and set(log.tags).intersection(rule.tag_filter))
    return False


async def _load_enabled_rules(session: AsyncSession) -> list[AlertRule]:
    if rules_cache.valid():
        return rules_cache._rules
    result = await session.execute(select(AlertRule).where(AlertRule.enabled.is_(True)).order_by(AlertRule.created_at.asc()))
    rules = list(result.scalars())
    rules_cache.set(rules)
    return rules


def _webhook_payload(rule: AlertRule, log: Log) -> dict:
    return {
        "text": f"[llmh] rule '{rule.name}' fired",
        "attachments": [
            {
                "title": f"{log.tool} on {log.source.name}",
                "text": log.message,
                "ts": int(log.occurred_at.timestamp()),
            }
        ],
    }


def _email_subject(rule: AlertRule, log: Log) -> str:
    return f"[llmh] {rule.name} fired on {log.source.name}"


def _email_body(rule: AlertRule, log: Log) -> str:
    return (
        f"Rule: {rule.name}\n"
        f"Source: {log.source.name}\n"
        f"Tool: {log.tool}\n"
        f"Level: {log.level}\n"
        f"Occurred: {log.occurred_at.isoformat()}\n"
        f"Message: {log.message}\n"
    )


async def evaluate_for(logs: list[Log], session: AsyncSession) -> None:
    if not logs:
        return
    rules = await _load_enabled_rules(session)
    for log in logs:
        if "source" not in log.__dict__:
            await session.refresh(log, attribute_names=["source"])
        for rule in rules:
            if not match(rule, log):
                continue
            event = AlertEvent(rule_id=rule.id, log_id=log.id, delivery_status={})
            session.add(event)
            await session.flush()
            metrics.inc("alert_events_total")
            delivery_status: dict = {}
            if rule.webhook_url:
                try:
                    delivery_status["webhook"] = await send_webhook(rule.webhook_url, _webhook_payload(rule, log))
                except Exception as exc:
                    delivery_status["webhook"] = {"error": str(exc)}
            if rule.email_to:
                try:
                    delivery_status["email"] = await send_email(
                        to_address=rule.email_to,
                        subject=_email_subject(rule, log),
                        body=_email_body(rule, log),
                    )
                except Exception as exc:
                    delivery_status["email"] = {"ok": False, "error": str(exc)}
            event.delivery_status = delivery_status
    await session.commit()


async def list_alert_events(
    session: AsyncSession,
    *,
    rule_id=None,
    from_=None,
    to=None,
    limit: int,
    offset: int,
) -> list[tuple[AlertEvent, AlertRule, Log]]:
    stmt = (
        select(AlertEvent, AlertRule, Log)
        .join(AlertRule, AlertRule.id == AlertEvent.rule_id)
        .join(Log, Log.id == AlertEvent.log_id)
        .options(selectinload(Log.source))
        .order_by(AlertEvent.fired_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if rule_id is not None:
        stmt = stmt.where(AlertEvent.rule_id == rule_id)
    if from_ is not None:
        stmt = stmt.where(AlertEvent.fired_at >= from_)
    if to is not None:
        stmt = stmt.where(AlertEvent.fired_at <= to)
    result = await session.execute(stmt)
    return list(result.all())
