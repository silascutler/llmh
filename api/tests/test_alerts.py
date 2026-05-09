from __future__ import annotations

from llmh.alerts.evaluator import clear_rule_cache
from llmh.db.models import AlertEvent, Source


async def test_matching_rule_fires_and_alerts_endpoint_lists_event(logged_in_admin, session, monkeypatch):
    delivered = {"webhook": None, "email": None}

    async def fake_webhook(url: str, payload: dict) -> dict:
        delivered["webhook"] = {"url": url, "payload": payload}
        return {"status_code": 200, "ms": 12}

    async def fake_email(*, to_address: str, subject: str, body: str) -> dict:
        delivered["email"] = {"to": to_address, "subject": subject, "body": body}
        return {"ok": True}

    monkeypatch.setattr("llmh.alerts.evaluator.send_webhook", fake_webhook)
    monkeypatch.setattr("llmh.alerts.evaluator.send_email", fake_email)
    clear_rule_cache()

    source = Source(name="laptop", hostname="silas-laptop", tags=["dev"])
    session.add(source)
    await session.commit()
    await session.refresh(source)

    create_rule = await logged_in_admin.post(
        "/rules",
        json={
            "name": "auth failures",
            "enabled": True,
            "match_type": "keyword",
            "match_value": "missing token",
            "source_filter": str(source.id),
            "tag_filter": ["build"],
            "webhook_url": "https://example.test/hook",
            "email_to": "ops@example.com",
        },
    )
    assert create_rule.status_code == 201

    ingest = await logged_in_admin.post(
        "/ingest",
        headers={"Authorization": "Bearer test-ingest-token"},
        json={
            "logs": [
                {
                    "source_id": str(source.id),
                    "tool": "claude-code",
                    "level": "error",
                    "message": "build failed: missing token",
                    "raw": {"argv": ["claude", "build"]},
                    "tags": ["build"],
                    "occurred_at": "2026-04-27T18:11:00Z",
                }
            ]
        },
    )
    assert ingest.status_code == 202

    alerts = await logged_in_admin.get("/alerts")
    assert alerts.status_code == 200
    items = alerts.json()
    assert len(items) == 1
    assert items[0]["rule_name"] == "auth failures"
    assert items[0]["log_message"] == "build failed: missing token"
    assert items[0]["delivery_status"]["webhook"]["status_code"] == 200
    assert items[0]["delivery_status"]["email"]["ok"] is True

    assert delivered["webhook"]["url"] == "https://example.test/hook"
    assert delivered["email"]["to"] == "ops@example.com"

    events = await session.execute(AlertEvent.__table__.select())
    assert len(events.all()) == 1


async def test_non_matching_rule_does_not_fire(logged_in_admin, session, monkeypatch):
    async def fake_webhook(url: str, payload: dict) -> dict:
        raise AssertionError("webhook should not be called")

    monkeypatch.setattr("llmh.alerts.evaluator.send_webhook", fake_webhook)
    clear_rule_cache()

    source = Source(name="laptop", hostname="silas-laptop", tags=["dev"])
    session.add(source)
    await session.commit()
    await session.refresh(source)

    create_rule = await logged_in_admin.post(
        "/rules",
        json={
            "name": "auth failures",
            "enabled": True,
            "match_type": "keyword",
            "match_value": "missing token",
            "webhook_url": "https://example.test/hook",
        },
    )
    assert create_rule.status_code == 201

    ingest = await logged_in_admin.post(
        "/ingest",
        headers={"Authorization": "Bearer test-ingest-token"},
        json={
            "logs": [
                {
                    "source_id": str(source.id),
                    "tool": "claude-code",
                    "level": "info",
                    "message": "all good",
                    "raw": {},
                    "tags": [],
                    "occurred_at": "2026-04-27T18:11:00Z",
                }
            ]
        },
    )
    assert ingest.status_code == 202
    alerts = await logged_in_admin.get("/alerts")
    assert alerts.status_code == 200
    assert alerts.json() == []
