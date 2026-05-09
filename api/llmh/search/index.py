from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from time import monotonic
from typing import Any

import httpx

from llmh.config import get_settings

INDEX_NAME = "logs"
MEILI_TASK_POLL_INTERVAL_SECONDS = 0.1
MEILI_TASK_TIMEOUT_SECONDS = 60.0


def _actor_for_sender(sender: str | None) -> str:
    if sender == "user":
        return "human"
    if sender == "assistant":
        return "assistant"
    if sender == "tool_result":
        return "tool"
    if sender == "system":
        return "system"
    return "other"


async def ensure_index() -> None:
    settings = get_settings()
    headers = {"Authorization": f"Bearer {settings.meili_master_key}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{settings.meili_url}/indexes/{INDEX_NAME}", headers=headers)
        if response.status_code == 404:
            create_response = await client.post(
                f"{settings.meili_url}/indexes",
                headers=headers,
                json={"uid": INDEX_NAME, "primaryKey": "id"},
            )
            create_response.raise_for_status()
            await _wait_for_task(client, create_response.json()["taskUid"], headers)
        settings_response = await client.patch(
            f"{settings.meili_url}/indexes/{INDEX_NAME}/settings",
            headers=headers,
            json={
                "searchableAttributes": [
                    "message",
                    "content_text",
                    "project_name",
                    "project_file",
                    "cwd",
                    "actor",
                    "sender",
                    "tool",
                    "source_name",
                    "tags",
                    "session_id",
                ],
                "filterableAttributes": ["source_id", "tool", "level", "actor", "tags", "occurred_at_ts", "session_id"],
                "sortableAttributes": [
                    "occurred_at_ts",
                    "received_at_ts",
                    "source_name",
                    "tool",
                    "level",
                    "message",
                    "tags_sort",
                ],
                "rankingRules": ["words", "typo", "proximity", "attribute", "sort", "exactness", "occurred_at_ts:desc"],
                "pagination": {"maxTotalHits": 10000},
            },
        )
        settings_response.raise_for_status()
        await _wait_for_task(client, settings_response.json()["taskUid"], headers)


def _ts(value: datetime) -> int:
    return int(value.astimezone(timezone.utc).timestamp())


def _meili_headers() -> dict[str, str]:
    settings = get_settings()
    return {"Authorization": f"Bearer {settings.meili_master_key}"}


async def _wait_for_task(
    client: httpx.AsyncClient,
    task_uid: int,
    headers: dict[str, str],
    *,
    poll_interval_seconds: float = MEILI_TASK_POLL_INTERVAL_SECONDS,
    timeout_seconds: float = MEILI_TASK_TIMEOUT_SECONDS,
) -> None:
    deadline = monotonic() + timeout_seconds
    while True:
        response = await client.get(f"{get_settings().meili_url}/tasks/{task_uid}", headers=headers)
        response.raise_for_status()
        task = response.json()
        status = task["status"]
        if status == "succeeded":
            return
        if status in {"failed", "canceled"}:
            raise RuntimeError(f"meilisearch task failed: {task}")
        if monotonic() >= deadline:
            raise TimeoutError(f"timed out waiting for meilisearch task {task_uid}: {task}")
        await asyncio.sleep(poll_interval_seconds)


async def clear_index() -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.delete(f"{get_settings().meili_url}/indexes/{INDEX_NAME}/documents", headers=_meili_headers())
        response.raise_for_status()
        await _wait_for_task(client, response.json()["taskUid"], _meili_headers())


async def delete_logs(log_ids: list[str]) -> None:
    if not log_ids:
        return
    headers = _meili_headers()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{get_settings().meili_url}/indexes/{INDEX_NAME}/documents/delete-batch",
            headers=headers,
            json=log_ids,
        )
        response.raise_for_status()
        await _wait_for_task(client, response.json()["taskUid"], headers)


def _doc_for_log(row: Any) -> dict[str, Any]:
    raw = row.raw if isinstance(row.raw, dict) else {}
    import_meta = raw.get("import", {}) if isinstance(raw.get("import"), dict) else {}
    sender = raw.get("sender", "")
    return {
        "id": str(row.id),
        "source_id": str(row.source_id),
        "source_name": row.source.name,
        "tool": row.tool,
        "actor": _actor_for_sender(sender),
        "session_id": row.session_id,
        "level": row.level,
        "message": row.message,
        "content_text": raw.get("content_text", ""),
        "project_name": raw.get("project_name", ""),
        "project_file": import_meta.get("project_file", ""),
        "cwd": raw.get("cwd", ""),
        "sender": sender,
        "tags": row.tags,
        "tags_sort": ", ".join(row.tags),
        "occurred_at_ts": _ts(row.occurred_at),
        "received_at_ts": _ts(row.received_at),
    }


async def index_logs(rows: list[Any]) -> None:
    if not rows:
        return
    headers = _meili_headers()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{get_settings().meili_url}/indexes/{INDEX_NAME}/documents",
            headers=headers,
            json=_doc_for_log_batch(rows),
        )
        response.raise_for_status()
        await _wait_for_task(client, response.json()["taskUid"], headers)


def _doc_for_log_batch(rows: list[Any]) -> list[dict[str, Any]]:
    return [_doc_for_log(row) for row in rows]


def _build_filter(
    source_id: str | None,
    tool: str | None,
    level: str | None,
    actors: list[str],
    tags: list[str],
    from_ts: int | None,
    to_ts: int | None,
    session_id: str | None,
) -> str | None:
    clauses: list[str] = []
    if source_id:
        clauses.append(f"source_id = '{source_id}'")
    if tool:
        clauses.append(f"tool = '{tool}'")
    if level:
        clauses.append(f"level = '{level}'")
    if actors:
        quoted_actors = ", ".join(f"'{actor}'" for actor in actors)
        clauses.append(f"actor IN [{quoted_actors}]")
    if session_id:
        clauses.append(f"session_id = '{session_id}'")
    if from_ts is not None:
        clauses.append(f"occurred_at_ts >= {from_ts}")
    if to_ts is not None:
        clauses.append(f"occurred_at_ts <= {to_ts}")
    if tags:
        quoted = ", ".join(f"'{tag}'" for tag in tags)
        clauses.append(f"tags IN [{quoted}]")
    return " AND ".join(clauses) if clauses else None


async def search_logs(
    *,
    q: str,
    source_id,
    tool,
    level,
    actors,
    tags,
    from_,
    to,
    session_id,
    sort_by: str,
    sort_dir: str,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    sort_field = {
        "occurred_at": "occurred_at_ts",
        "source_name": "source_name",
        "tool": "tool",
        "level": "level",
        "message": "message",
        "tags": "tags_sort",
    }[sort_by]
    headers = _meili_headers()
    payload: dict[str, Any] = {
        "q": q,
        "sort": [f"{sort_field}:{sort_dir}"],
        "limit": limit,
        "offset": offset,
    }
    filter_expr = _build_filter(
        str(source_id) if source_id else None,
        tool,
        level,
        actors,
        tags,
        _ts(from_) if from_ else None,
        _ts(to) if to else None,
        session_id,
    )
    if filter_expr:
        payload["filter"] = filter_expr
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{get_settings().meili_url}/indexes/{INDEX_NAME}/search",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
    ids = [hit["id"] for hit in body.get("hits", [])]
    return {
        "ids": ids,
        "estimated_total": int(body.get("estimatedTotalHits", 0)),
        "has_more": offset + len(ids) < int(body.get("estimatedTotalHits", 0)),
    }
