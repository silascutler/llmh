from __future__ import annotations

from sqlalchemy import select

from llmh.db.models import Log, Source
from llmh.search.index import index_logs


async def test_ingest_persists_logs_and_auto_creates_source(client):
    response = await client.post(
        "/ingest",
        headers={"Authorization": "Bearer test-ingest-token"},
        json={
            "logs": [
                {
                    "source_key": {
                        "hostname": "host-a",
                        "ip_address": "10.0.0.9",
                        "port": 22,
                        "name": "laptop-a",
                        "tags": ["dev"],
                    },
                    "tool": "codex",
                    "level": "info",
                    "message": "ship it",
                    "raw": {"argv": ["codex"]},
                    "tags": ["build"],
                    "occurred_at": "2026-04-27T18:11:00Z",
                }
            ]
        },
    )
    assert response.status_code == 202
    assert len(response.json()["ids"]) == 1


async def test_ingest_source_id_and_search_path(logged_in_admin, session):
    source = Source(name="laptop", hostname="silas-laptop", tags=["dev"])
    session.add(source)
    await session.commit()
    await session.refresh(source)

    ingest = await logged_in_admin.post(
        "/ingest",
        headers={"Authorization": "Bearer test-ingest-token"},
        json={
            "logs": [
                {
                    "source_id": str(source.id),
                    "tool": "claude-code",
                    "session_id": "abc123",
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

    log_result = await session.execute(select(Log))
    log_rows = list(log_result.scalars())
    for row in log_rows:
        await session.refresh(row, attribute_names=["source"])
    await index_logs(log_rows)

    search = await logged_in_admin.get("/logs", params={"q": "missing token"})
    assert search.status_code == 200
    body = search.json()
    assert body["estimated_total"] == 1
    assert body["items"][0]["source_name"] == "laptop"
    assert body["items"][0]["session_id"] == "abc123"

    result = await session.execute(select(Log))
    rows = list(result.scalars())
    assert len(rows) == 1


async def test_ingest_queues_indexing_for_worker(client, redis, session):
    response = await client.post(
        "/ingest",
        headers={"Authorization": "Bearer test-ingest-token"},
        json={
            "logs": [
                {
                    "source_key": {
                        "hostname": "host-a",
                        "ip_address": "10.0.0.9",
                        "port": 22,
                        "name": "laptop-a",
                        "tags": ["dev"],
                    },
                    "tool": "codex",
                    "level": "info",
                    "message": "ship it",
                    "raw": {"argv": ["codex"]},
                    "tags": ["build"],
                    "occurred_at": "2026-04-27T18:11:00Z",
                }
            ]
        },
    )
    assert response.status_code == 202
    assert len(response.json()["ids"]) == 1

    retry_len = await redis.llen("llmh:meili:retry")
    assert retry_len == 1

    result = await session.execute(select(Log))
    rows = list(result.scalars())
    assert len(rows) == 1


async def test_ingest_rejects_missing_token(client):
    response = await client.post("/ingest", json={"logs": []})
    assert response.status_code == 401


async def test_source_key_resolves_by_name_across_tools(client, session):
    headers = {"Authorization": "Bearer test-ingest-token"}

    codex_resp = await client.post(
        "/ingest",
        headers=headers,
        json={
            "logs": [
                {
                    "source_key": {"name": "athena", "hostname": "athena", "ip_address": None, "port": None, "tags": ["host"]},
                    "tool": "codex",
                    "level": "info",
                    "message": "codex log",
                    "raw": {},
                    "occurred_at": "2026-04-28T12:00:00Z",
                }
            ]
        },
    )
    assert codex_resp.status_code == 202

    claude_resp = await client.post(
        "/ingest",
        headers=headers,
        json={
            "logs": [
                {
                    "source_key": {"name": "athena", "hostname": "athena-host", "ip_address": "10.0.0.5", "port": 8080, "tags": []},
                    "tool": "claude-code",
                    "level": "info",
                    "message": "claude log",
                    "raw": {},
                    "occurred_at": "2026-04-28T12:01:00Z",
                }
            ]
        },
    )
    assert claude_resp.status_code == 202

    result = await session.execute(select(Source).where(Source.name == "athena"))
    sources = list(result.scalars())
    assert len(sources) == 1, f"expected one athena source, got {len(sources)}"
    assert sources[0].hostname == "athena"
    assert str(sources[0].ip_address) == "10.0.0.5"
    assert sources[0].port == 8080

    logs_result = await session.execute(select(Log).where(Log.source_id == sources[0].id))
    logs = list(logs_result.scalars())
    assert {row.tool for row in logs} == {"codex", "claude-code"}
