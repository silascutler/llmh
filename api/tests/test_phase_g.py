from __future__ import annotations

import asyncio

from sqlalchemy import select

from llmh.alerts.evaluator import clear_rule_cache, rules_cache
from llmh.db.models import AlertRule, Log, Source
from llmh.metrics import metrics
from llmh.rule_notifications import RuleNotificationListener, notify_rules_changed


async def test_ingest_idempotency_key_deduplicates(logged_in_admin, session):
    source = Source(name="laptop", hostname="silas-laptop", tags=["dev"])
    session.add(source)
    await session.commit()
    await session.refresh(source)

    payload = {
        "source_id": str(source.id),
        "tool": "codex",
        "session_id": "dup-test",
        "idempotency_key": "dup-001",
        "level": "info",
        "message": "same line",
        "raw": {"line": "same line"},
        "tags": ["dup"],
        "occurred_at": "2026-04-28T04:00:00Z",
    }

    first = await logged_in_admin.post("/ingest", headers={"Authorization": "Bearer test-ingest-token"}, json={"logs": [payload]})
    second = await logged_in_admin.post("/ingest", headers={"Authorization": "Bearer test-ingest-token"}, json={"logs": [payload]})

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["ids"] == second.json()["ids"]

    result = await session.execute(select(Log).where(Log.session_id == "dup-test"))
    rows = list(result.scalars())
    assert len(rows) == 1
    assert rows[0].idempotency_key == "dup-001"


async def test_metrics_endpoint_exposes_counters(logged_in_admin):
    response = await logged_in_admin.get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert "llmh_http_requests_total" in body

    ingest = await logged_in_admin.post(
        "/ingest",
        headers={"Authorization": "Bearer test-ingest-token"},
        json={
            "logs": [
                {
                    "source_key": {
                        "hostname": "metrics-host",
                        "name": "metrics-source",
                    },
                    "tool": "codex",
                    "idempotency_key": "metrics-1",
                    "level": "info",
                    "message": "metrics line",
                    "raw": {},
                    "tags": [],
                    "occurred_at": "2026-04-28T04:00:00Z",
                }
            ]
        },
    )
    assert ingest.status_code == 202

    metrics_response = await logged_in_admin.get("/metrics")
    body = metrics_response.text
    assert "llmh_logs_ingested_total" in body
    assert 'llmh_http_requests_total{method="GET",path="/metrics",status_code="200"}' in body
    assert metrics._counters  # confirms the store is populated for the endpoint render path


async def test_rule_notifications_clear_cache(session, admin_user):
    clear_rule_cache()
    listener = RuleNotificationListener()
    await listener.start()
    try:
        rule = AlertRule(
            name="cache test",
            enabled=True,
            match_type="keyword",
            match_value="boom",
            created_by=admin_user.id,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)

        rules_cache.set([rule])
        assert rules_cache.valid()

        await notify_rules_changed()

        for _ in range(20):
            if not rules_cache.valid():
                break
            await asyncio.sleep(0.05)

        assert not rules_cache.valid()
    finally:
        await listener.stop()
