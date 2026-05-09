from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from scripts.reindex_meili import reindex

from llmh.db.models import Log, Source
from llmh.search.index import _wait_for_task, index_logs


async def test_recent_logs_path_bypasses_query_and_orders_desc(logged_in_admin, session):
    source = Source(name="laptop", hostname="silas-laptop", tags=[])
    session.add(source)
    await session.flush()

    now = datetime.now(timezone.utc)
    older = Log(source=source, source_id=source.id, tool="codex", level="info", message="older", raw={}, tags=[], occurred_at=now - timedelta(minutes=2))
    newer = Log(source=source, source_id=source.id, tool="codex", level="warn", message="newer", raw={}, tags=[], occurred_at=now - timedelta(minutes=1))
    session.add_all([older, newer])
    await session.commit()

    response = await logged_in_admin.get("/logs")
    assert response.status_code == 200
    body = response.json()
    items = body["items"]
    assert [item["message"] for item in items] == ["newer", "older"]
    assert body["estimated_total"] == 2


async def test_filtered_search_uses_meili_and_tags(logged_in_admin, session):
    source = Source(name="laptop", hostname="silas-laptop", tags=["dev"])
    session.add(source)
    await session.flush()
    match = Log(
        source=source,
        source_id=source.id,
        tool="codex",
        level="error",
        message="missing token during build",
        raw={},
        tags=["build"],
        occurred_at=datetime(2026, 4, 27, 18, 11, 0, tzinfo=timezone.utc),
    )
    miss = Log(
        source=source,
        source_id=source.id,
        tool="codex",
        level="info",
        message="everything fine",
        raw={},
        tags=["runtime"],
        occurred_at=datetime(2026, 4, 27, 18, 12, 0, tzinfo=timezone.utc),
    )
    session.add_all([match, miss])
    await session.commit()
    await session.refresh(match, attribute_names=["source"])
    await session.refresh(miss, attribute_names=["source"])
    await index_logs([match, miss])

    response = await logged_in_admin.get("/logs", params={"q": "missing token", "tags": ["build"], "level": "error"})
    assert response.status_code == 200
    body = response.json()
    assert body["estimated_total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["message"] == "missing token during build"


async def test_search_indexes_imported_content_text(logged_in_admin, session):
    source = Source(name="archive-host", hostname="archive-host", tags=["imported"])
    session.add(source)
    await session.flush()
    row = Log(
        source=source,
        source_id=source.id,
        tool="claude-code",
        level="info",
        message="assistant: startup banner",
        raw={
            "sender": "assistant",
            "cwd": "/root/project",
            "project_name": "project",
            "content_text": "I understand. I'm ready to explore codebases and design implementation plans in read-only mode.",
            "import": {"project_file": "projects/-root/session.jsonl"},
        },
        tags=["imported", "claude-archive"],
        occurred_at=datetime(2026, 4, 27, 18, 13, 0, tzinfo=timezone.utc),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row, attribute_names=["source"])
    await index_logs([row])

    response = await logged_in_admin.get("/logs", params={"q": "design implementation plans in read-only mode"})
    assert response.status_code == 200
    body = response.json()
    assert body["estimated_total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(row.id)


async def test_sessions_endpoint_returns_recent_session_summaries(logged_in_admin, session):
    source = Source(name="archive-host", hostname="archive-host", tags=["imported"])
    session.add(source)
    await session.flush()
    now = datetime(2026, 4, 27, 18, 30, 0, tzinfo=timezone.utc)
    session.add_all(
        [
            Log(
                source=source,
                source_id=source.id,
                tool="claude-code",
                session_id="session-a",
                level="info",
                message="first line",
                raw={},
                tags=[],
                occurred_at=now - timedelta(minutes=2),
            ),
            Log(
                source=source,
                source_id=source.id,
                tool="claude-code",
                session_id="session-a",
                level="info",
                message="latest line",
                raw={},
                tags=[],
                occurred_at=now - timedelta(minutes=1),
            ),
            Log(
                source=source,
                source_id=source.id,
                tool="claude-code",
                session_id="session-b",
                level="info",
                message="other session",
                raw={},
                tags=[],
                occurred_at=now - timedelta(minutes=3),
            ),
        ]
    )
    await session.commit()

    response = await logged_in_admin.get("/logs/sessions", params={"tool": "claude-code"})
    assert response.status_code == 200
    body = response.json()
    assert [item["session_id"] for item in body["items"][:2]] == ["session-a", "session-b"]
    assert body["items"][0]["log_count"] == 2
    assert body["items"][0]["preview"] == "latest line"
    assert body["items"][0]["source_name"] == "archive-host"


async def test_sessions_endpoint_supports_oldest_first_sort(logged_in_admin, session):
    source = Source(name="archive-host", hostname="archive-host", tags=["imported"])
    session.add(source)
    await session.flush()
    now = datetime(2026, 4, 27, 18, 30, 0, tzinfo=timezone.utc)
    session.add_all(
        [
            Log(
                source=source,
                source_id=source.id,
                tool="claude-code",
                session_id="session-a",
                level="info",
                message="newer session",
                raw={},
                tags=[],
                occurred_at=now - timedelta(minutes=1),
            ),
            Log(
                source=source,
                source_id=source.id,
                tool="claude-code",
                session_id="session-b",
                level="info",
                message="older session",
                raw={},
                tags=[],
                occurred_at=now - timedelta(minutes=3),
            ),
        ]
    )
    await session.commit()

    response = await logged_in_admin.get("/logs/sessions", params={"tool": "claude-code", "sort_dir": "asc"})
    assert response.status_code == 200
    body = response.json()
    assert [item["session_id"] for item in body["items"][:2]] == ["session-b", "session-a"]


async def test_filtered_logs_without_query_use_database_filters(logged_in_admin, session):
    source = Source(name="archive-host", hostname="archive-host", tags=["imported"])
    session.add(source)
    await session.flush()
    now = datetime(2026, 4, 27, 18, 45, 0, tzinfo=timezone.utc)
    wanted = Log(
        source=source,
        source_id=source.id,
        tool="claude-code",
        session_id="session-a",
        level="info",
        message="wanted",
        raw={},
        tags=["imported"],
        occurred_at=now,
    )
    other = Log(
        source=source,
        source_id=source.id,
        tool="claude-code",
        session_id="session-b",
        level="info",
        message="other",
        raw={},
        tags=["imported"],
        occurred_at=now - timedelta(minutes=1),
    )
    session.add_all([wanted, other])
    await session.commit()

    response = await logged_in_admin.get(
        "/logs",
        params={"source_id": str(source.id), "session_id": "session-a", "limit": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["estimated_total"] == 1
    assert [item["message"] for item in body["items"]] == ["wanted"]


async def test_logs_support_actor_filter_for_db_and_sessions(logged_in_admin, session):
    source = Source(name="archive-host", hostname="archive-host", tags=["imported"])
    session.add(source)
    await session.flush()
    now = datetime(2026, 4, 27, 18, 45, 0, tzinfo=timezone.utc)
    user_log = Log(
        source=source,
        source_id=source.id,
        tool="claude-code",
        session_id="session-a",
        level="info",
        message="user: question",
        raw={"sender": "user"},
        tags=["imported"],
        occurred_at=now,
    )
    assistant_log = Log(
        source=source,
        source_id=source.id,
        tool="claude-code",
        session_id="session-a",
        level="info",
        message="assistant: answer",
        raw={"sender": "assistant"},
        tags=["imported"],
        occurred_at=now + timedelta(seconds=1),
    )
    tool_log = Log(
        source=source,
        source_id=source.id,
        tool="claude-code",
        session_id="session-b",
        level="info",
        message="tool_result: output",
        raw={"sender": "tool_result"},
        tags=["imported"],
        occurred_at=now + timedelta(seconds=2),
    )
    session.add_all([user_log, assistant_log, tool_log])
    await session.commit()

    response = await logged_in_admin.get("/logs", params={"actor": "assistant", "limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["estimated_total"] == 1
    assert body["items"][0]["message"] == "assistant: answer"
    assert body["items"][0]["actor"] == "assistant"

    sessions_response = await logged_in_admin.get("/logs/sessions", params={"actor": "tool"})
    assert sessions_response.status_code == 200
    sessions_body = sessions_response.json()
    assert [item["session_id"] for item in sessions_body["items"]] == ["session-b"]

    multi_response = await logged_in_admin.get("/logs", params=[("actor", "human"), ("actor", "assistant"), ("limit", "10")])
    assert multi_response.status_code == 200
    multi_body = multi_response.json()
    assert multi_body["estimated_total"] == 2
    assert [item["actor"] for item in multi_body["items"]] == ["assistant", "human"]

    multi_sessions_response = await logged_in_admin.get("/logs/sessions", params=[("actor", "human"), ("actor", "assistant")])
    assert multi_sessions_response.status_code == 200
    multi_sessions_body = multi_sessions_response.json()
    assert [item["session_id"] for item in multi_sessions_body["items"]] == ["session-a"]


async def test_sessions_list_is_filtered_by_query_text(logged_in_admin, session):
    source = Source(name="archive-host", hostname="archive-host", tags=["imported"])
    session.add(source)
    await session.flush()
    matching = Log(
        source=source,
        source_id=source.id,
        tool="claude-code",
        session_id="session-match",
        level="info",
        message="assistant: design implementation plans",
        raw={"content_text": "assistant: design implementation plans"},
        tags=["imported"],
        occurred_at=datetime(2026, 4, 27, 18, 45, 0, tzinfo=timezone.utc),
    )
    other = Log(
        source=source,
        source_id=source.id,
        tool="claude-code",
        session_id="session-other",
        level="info",
        message="assistant: unrelated note",
        raw={"content_text": "assistant: unrelated note"},
        tags=["imported"],
        occurred_at=datetime(2026, 4, 27, 18, 46, 0, tzinfo=timezone.utc),
    )
    session.add_all([matching, other])
    await session.commit()

    response = await logged_in_admin.get("/logs/sessions", params={"q": "design implementation plans"})
    assert response.status_code == 200
    body = response.json()
    assert [item["session_id"] for item in body["items"]] == ["session-match"]


async def test_filtered_search_uses_requested_server_side_sort(logged_in_admin, session):
    source_a = Source(name="alpha", hostname="alpha-host", tags=[])
    source_b = Source(name="zeta", hostname="zeta-host", tags=[])
    session.add_all([source_a, source_b])
    await session.flush()
    row_a = Log(
        source=source_a,
        source_id=source_a.id,
        tool="claude-code",
        session_id="session-a",
        level="info",
        message="design implementation plans",
        raw={"content_text": "design implementation plans"},
        tags=[],
        occurred_at=datetime(2026, 4, 27, 18, 50, 0, tzinfo=timezone.utc),
    )
    row_b = Log(
        source=source_b,
        source_id=source_b.id,
        tool="claude-code",
        session_id="session-b",
        level="info",
        message="design implementation plans",
        raw={"content_text": "design implementation plans"},
        tags=[],
        occurred_at=datetime(2026, 4, 27, 18, 51, 0, tzinfo=timezone.utc),
    )
    session.add_all([row_a, row_b])
    await session.commit()
    await session.refresh(row_a, attribute_names=["source"])
    await session.refresh(row_b, attribute_names=["source"])
    await index_logs([row_a, row_b])

    response = await logged_in_admin.get(
        "/logs",
        params={"q": "design implementation plans", "sort_by": "source_name", "sort_dir": "asc", "limit": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert [item["source_name"] for item in body["items"][:2]] == ["alpha", "zeta"]


async def test_quoted_query_falls_back_to_database_text_search(logged_in_admin, session):
    source = Source(name="archive-host", hostname="archive-host", tags=["imported"])
    session.add(source)
    await session.flush()
    row = Log(
        source=source,
        source_id=source.id,
        tool="claude-code",
        session_id="session-quoted",
        level="info",
        message="assistant: follow-up",
        raw={"content_text": "Este es un programa de bug bounty oficial del SAT."},
        tags=["imported"],
        occurred_at=datetime(2026, 4, 27, 18, 55, 0, tzinfo=timezone.utc),
    )
    session.add(row)
    await session.commit()

    response = await logged_in_admin.get("/logs", params={"q": '"programa de bug bounty"', "limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["estimated_total"] == 1
    assert [item["id"] for item in body["items"]] == [str(row.id)]


async def test_reindex_backfills_all_logs_with_same_received_at(logged_in_admin, session):
    source = Source(name="archive-host", hostname="archive-host", tags=["imported"])
    session.add(source)
    await session.flush()
    shared_received_at = datetime(2026, 4, 27, 19, 0, 0, tzinfo=timezone.utc)
    rows = [
        Log(
            source=source,
            source_id=source.id,
            tool="claude-code",
            session_id=f"session-{index}",
            level="info",
            message=f"shared marker {index}",
            raw={"content_text": f"shared marker {index}"},
            tags=[],
            occurred_at=shared_received_at + timedelta(seconds=index),
            received_at=shared_received_at,
        )
        for index in range(3)
    ]
    session.add_all(rows)
    await session.commit()

    await reindex()

    response = await logged_in_admin.get("/logs", params={"q": "shared marker", "limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["estimated_total"] == 3
    assert {item["message"] for item in body["items"]} == {"shared marker 0", "shared marker 1", "shared marker 2"}


class _MeiliTaskResponse:
    def __init__(self, status: str) -> None:
        self._status = status

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"status": self._status}


class _MeiliTaskClient:
    def __init__(self, statuses: list[str]) -> None:
        self._statuses = statuses
        self.calls = 0

    async def get(self, *_args, **_kwargs) -> _MeiliTaskResponse:
        status = self._statuses[min(self.calls, len(self._statuses) - 1)]
        self.calls += 1
        return _MeiliTaskResponse(status)


async def test_wait_for_task_polls_with_backoff_until_success():
    client = _MeiliTaskClient(["enqueued", "processing", "succeeded"])

    await _wait_for_task(client, 123, {}, poll_interval_seconds=0, timeout_seconds=1)

    assert client.calls == 3


async def test_wait_for_task_times_out_instead_of_polling_forever():
    client = _MeiliTaskClient(["processing"])

    with pytest.raises(TimeoutError):
        await _wait_for_task(client, 123, {}, poll_interval_seconds=0, timeout_seconds=0)

    assert client.calls == 1
