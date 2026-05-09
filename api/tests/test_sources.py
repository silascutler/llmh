from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from uuid import UUID

from llmh.db.models import Log


async def test_admin_can_create_and_list_sources(logged_in_admin):
    response = await logged_in_admin.post(
        "/sources",
        json={
            "name": "laptop",
            "hostname": "silas-laptop",
            "ip_address": "10.0.0.5",
            "port": 22,
            "notes": "office",
            "tags": ["dev", "personal"],
        },
    )
    assert response.status_code == 201
    created = response.json()
    assert created["hostname"] == "silas-laptop"
    assert created["log_count"] == 0
    assert created["session_count"] == 0

    listed = await logged_in_admin.get("/sources")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["log_count"] == 0
    assert listed.json()[0]["session_count"] == 0


async def test_source_can_be_created_without_hostname(logged_in_admin):
    response = await logged_in_admin.post(
        "/sources",
        json={
            "name": "archive-host",
            "ip_address": "10.0.0.10",
            "port": 2222,
            "tags": ["imported"],
        },
    )
    assert response.status_code == 201
    created = response.json()
    assert created["hostname"] == "archive-host"


async def test_source_hostname_can_be_cleared(logged_in_admin):
    create = await logged_in_admin.post(
        "/sources",
        json={"name": "laptop", "hostname": "wrong-host", "ip_address": "10.0.0.5", "port": 22, "tags": []},
    )
    assert create.status_code == 201
    source_id = create.json()["id"]

    updated = await logged_in_admin.patch(f"/sources/{source_id}", json={"hostname": None})
    assert updated.status_code == 200
    assert updated.json()["hostname"] is None

    detail = await logged_in_admin.get(f"/sources/{source_id}")
    assert detail.status_code == 200
    assert detail.json()["hostname"] is None


async def test_viewer_cannot_create_source(logged_in_viewer):
    response = await logged_in_viewer.post(
        "/sources",
        json={"name": "laptop", "hostname": "silas-laptop", "tags": []},
    )
    assert response.status_code == 403


async def test_source_detail_includes_last_seen(logged_in_admin, session):
    create = await logged_in_admin.post(
        "/sources",
        json={"name": "laptop", "hostname": "silas-laptop", "ip_address": "10.0.0.5", "port": 22, "tags": ["dev"]},
    )
    source_id = create.json()["id"]

    session.add(
        Log(
            source_id=UUID(source_id),
            tool="codex",
            session_id="sess-1",
            level="info",
            message="hello",
            raw={},
            tags=[],
            occurred_at=datetime(2026, 4, 27, 18, 11, 0, tzinfo=timezone.utc),
        )
    )
    await session.commit()

    response = await logged_in_admin.get(f"/sources/{source_id}")
    assert response.status_code == 200
    assert response.json()["last_seen_at"] == "2026-04-27T18:11:00Z"
    assert response.json()["log_count"] == 1
    assert response.json()["session_count"] == 1


async def test_source_list_includes_total_log_count(logged_in_admin, session):
    create = await logged_in_admin.post(
        "/sources",
        json={"name": "laptop", "hostname": "silas-laptop", "tags": ["dev"]},
    )
    source_id = create.json()["id"]

    session.add_all(
        [
            Log(
                source_id=UUID(source_id),
                tool="codex",
                session_id="sess-1",
                level="info",
                message="hello",
                raw={},
                tags=[],
                occurred_at=datetime(2026, 4, 27, 18, 11, 0, tzinfo=timezone.utc),
            ),
            Log(
                source_id=UUID(source_id),
                tool="codex",
                session_id="sess-2",
                level="warn",
                message="world",
                raw={},
                tags=[],
                occurred_at=datetime(2026, 4, 27, 18, 12, 0, tzinfo=timezone.utc),
            ),
        ]
    )
    await session.commit()

    listed = await logged_in_admin.get("/sources")
    assert listed.status_code == 200
    assert listed.json()[0]["log_count"] == 2
    assert listed.json()[0]["session_count"] == 2


async def test_source_stats_include_all_logs(logged_in_admin, session):
    create = await logged_in_admin.post(
        "/sources",
        json={"name": "laptop", "hostname": "silas-laptop", "tags": ["dev"]},
    )
    source_id = create.json()["id"]

    session.add_all(
        [
            Log(
                source_id=UUID(source_id),
                tool="codex",
                session_id="sess-1",
                level="debug",
                message="dbg",
                raw={},
                tags=[],
                occurred_at=datetime(2026, 1, 1, 18, 11, 0, tzinfo=timezone.utc),
            ),
            Log(
                source_id=UUID(source_id),
                tool="codex",
                session_id="sess-2",
                level="info",
                message="inf",
                raw={},
                tags=[],
                occurred_at=datetime(2026, 1, 2, 18, 11, 0, tzinfo=timezone.utc),
            ),
            Log(
                source_id=UUID(source_id),
                tool="codex",
                session_id="sess-3",
                level="warn",
                message="wrn",
                raw={},
                tags=[],
                occurred_at=datetime(2026, 4, 1, 18, 11, 0, tzinfo=timezone.utc),
            ),
            Log(
                source_id=UUID(source_id),
                tool="codex",
                session_id="sess-4",
                level="error",
                message="err",
                raw={},
                tags=[],
                occurred_at=datetime(2026, 4, 26, 4, 3, 4, tzinfo=timezone.utc),
            ),
        ]
    )
    await session.commit()

    response = await logged_in_admin.get(f"/sources/{source_id}/stats")
    assert response.status_code == 200
    assert response.json() == {"debug": 1, "info": 1, "warn": 1, "error": 1}


async def test_duplicate_source_returns_conflict(logged_in_admin):
    payload = {"name": "laptop", "hostname": "silas-laptop", "ip_address": "10.0.0.5", "port": 22, "tags": []}
    first = await logged_in_admin.post("/sources", json=payload)
    assert first.status_code == 201
    second = await logged_in_admin.post("/sources", json=payload)
    assert second.status_code == 409


async def test_delete_source_removes_associated_logs(logged_in_admin, session):
    create = await logged_in_admin.post(
        "/sources",
        json={"name": "laptop", "hostname": "silas-laptop", "tags": ["dev"]},
    )
    source_id = create.json()["id"]

    session.add(
        Log(
            source_id=UUID(source_id),
            tool="codex",
            level="info",
            message="hello",
            raw={"content_text": "hello"},
            tags=[],
            occurred_at=datetime(2026, 4, 27, 18, 11, 0, tzinfo=timezone.utc),
        )
    )
    await session.commit()

    deleted = await logged_in_admin.delete(f"/sources/{source_id}")
    assert deleted.status_code == 204

    logs = await logged_in_admin.get(f"/logs?source_id={source_id}")
    assert logs.status_code == 200
    assert logs.json()["estimated_total"] == 0
    assert logs.json()["items"] == []


async def test_export_source_returns_zip_archive(logged_in_admin, session):
    create = await logged_in_admin.post(
        "/sources",
        json={"name": "laptop", "hostname": "silas-laptop", "ip_address": "10.0.0.5", "port": 22, "tags": ["dev"]},
    )
    source_id = create.json()["id"]

    session.add(
        Log(
            source_id=UUID(source_id),
            tool="claude-code",
            session_id="sess-1",
            level="info",
            message="assistant: hello",
            raw={"content_text": "hello", "sender": "assistant"},
            tags=["imported"],
            occurred_at=datetime(2026, 4, 27, 18, 11, 0, tzinfo=timezone.utc),
        )
    )
    await session.commit()

    exported = await logged_in_admin.get(f"/sources/{source_id}/export")
    assert exported.status_code == 200
    assert exported.headers["content-type"] == "application/zip"
    assert "attachment;" in exported.headers["content-disposition"]

    archive = zipfile.ZipFile(io.BytesIO(exported.content))
    assert sorted(archive.namelist()) == ["logs.jsonl", "source.json"]

    source_payload = json.loads(archive.read("source.json").decode("utf-8"))
    assert source_payload["source"]["id"] == source_id
    assert source_payload["source"]["ip_address"] == "10.0.0.5"
    assert source_payload["log_count"] == 1

    logs_text = archive.read("logs.jsonl").decode("utf-8").strip().splitlines()
    assert len(logs_text) == 1
    log_payload = json.loads(logs_text[0])
    assert log_payload["session_id"] == "sess-1"
    assert log_payload["raw"]["content_text"] == "hello"
