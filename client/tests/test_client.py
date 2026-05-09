from __future__ import annotations

import json
from pathlib import Path

import httpx

from llmh_client.__main__ import ScanConfig, compact_for_upload, run_scan
from llmh_client.claude_archive import (
    find_source_dir,
    is_claude_project_file,
    iter_project_files,
    parse_source_dir,
    resolve_scan_root,
)


def test_resolve_scan_root_finds_enclosing_source_dir() -> None:
    scan_path = Path("/tmp/import/185.237.218.186_8080/185.237.218.186:8080")

    resolved, source = resolve_scan_root(scan_path)

    assert resolved == Path("/tmp/import/185.237.218.186_8080")
    assert source == parse_source_dir(Path("/tmp/import/185.237.218.186_8080"))


def test_iter_project_files_only_keeps_claude_project_logs(tmp_path: Path) -> None:
    source_dir = tmp_path / "185.237.218.186_8080"
    claude_file = source_dir / "projects" / "-root" / "session.jsonl"
    ignored_file = source_dir / "sessions" / "ignored.jsonl"
    bad_file = source_dir / "projects" / "-root" / "not-claude.jsonl"
    claude_file.parent.mkdir(parents=True)
    ignored_file.parent.mkdir(parents=True)
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    claude_file.write_text(json.dumps({"type": "user", "message": {"role": "user", "content": "hello"}}) + "\n", encoding="utf-8")
    ignored_file.write_text(json.dumps({"type": "user"}) + "\n", encoding="utf-8")
    bad_file.write_text(json.dumps({"foo": "bar"}) + "\n", encoding="utf-8")

    assert is_claude_project_file(claude_file) is True
    assert iter_project_files(source_dir) == [claude_file]
    assert find_source_dir(claude_file) == source_dir


def test_run_scan_uploads_batched_claude_logs(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "185.237.218.186_8080"
    nested_root = source_dir / "185.237.218.186:8080"
    project_file = source_dir / "projects" / "-root" / "session.jsonl"
    project_file.parent.mkdir(parents=True)
    nested_root.mkdir(parents=True)
    project_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "message": {"role": "user", "content": "investigate target"},
                        "sessionId": "sess-1",
                        "timestamp": "2026-04-24T16:02:53.261Z",
                        "cwd": "/root/work",
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {"role": "assistant", "content": [{"type": "text", "text": "working on it"}]},
                        "sessionId": "sess-1",
                        "timestamp": "2026-04-24T16:02:54.261Z",
                        "cwd": "/root/work",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ingest"
        body = json.loads(request.content.decode("utf-8"))
        calls.append(body)
        return httpx.Response(200, json={"ids": ["1", "2"]})

    real_client = httpx.Client

    class MockClient:
        def __init__(self, **_: object) -> None:
            self._client = real_client(transport=httpx.MockTransport(handler), base_url="http://test")

        def post(self, *args, **kwargs):
            return self._client.post(*args, **kwargs)

        def close(self) -> None:
            self._client.close()

    monkeypatch.setattr("llmh_client.__main__.httpx.Client", MockClient)

    totals = run_scan(
        ScanConfig(
            api_url="http://test",
            token="token",
            source_name="archive-prod",
            hostname="archive-prod",
            scan_path=nested_root,
            batch_size=10,
            raw_payload_max_bytes=65536,
            request_target_bytes=512 * 1024,
            dry_run=False,
            tags=["imported", "claude-archive"],
        )
    )

    assert totals["files"] == 1
    assert totals["lines"] == 2
    assert totals["uploaded"] == 2
    assert totals["skipped"] == 0
    assert totals["truncated"] == 0
    assert len(calls) == 1
    payload = calls[0]["logs"]
    assert payload[0]["source_key"]["name"] == "archive-prod"
    assert payload[0]["source_key"]["ip_address"] == "185.237.218.186"
    assert payload[0]["source_key"]["port"] == 8080
    assert payload[0]["session_id"] == "sess-1"
    assert payload[0]["raw"]["content_text"] == "investigate target"
    assert payload[1]["message"].startswith("assistant: working on it")


def test_compact_for_upload_preserves_content_text_when_raw_is_too_large() -> None:
    payload = {
        "raw": {
            "import": {"format": "claude-project-jsonl"},
            "sender": "assistant",
            "record_type": "assistant",
            "session_id": "sess-1",
            "cwd": "/root/work",
            "project_name": "work",
            "content_text": "A" * 4000,
            "tool_input": {"command": "echo hi"},
            "tool_result": "B" * 8000,
            "record": {"blob": "C" * 12000},
        }
    }

    compacted = compact_for_upload(payload, max_raw_bytes=4096)

    assert compacted["raw"]["content_text"].startswith("A" * 100)
    assert compacted["raw"]["sender"] == "assistant"
    assert compacted["raw"]["session_id"] == "sess-1"
    assert compacted["raw"]["truncated"] is True
    assert "tool_result" not in compacted["raw"] or compacted["raw"]["tool_result"] == "<truncated:tool_result>"


def test_run_scan_auto_detects_mixed_archive_types(tmp_path: Path, monkeypatch) -> None:
    claude_source = tmp_path / "185.237.218.186_8080"
    claude_file = claude_source / "projects" / "-root" / "session.jsonl"
    codex_file = tmp_path / ".codex" / "sessions" / "2026" / "03" / "20" / "rollout-2026-03-20T00-06-41-019d096c-895b-78c3-9f34-b5dabf10e089.jsonl"
    claude_file.parent.mkdir(parents=True)
    codex_file.parent.mkdir(parents=True)
    claude_file.write_text(
        json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": "investigate target"},
                "sessionId": "claude-session-1",
                "timestamp": "2026-04-24T16:02:53.261Z",
                "cwd": "/root/work",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    codex_file.write_text(
        json.dumps(
            {
                "timestamp": "2026-03-20T04:07:01.368Z",
                "type": "session_meta",
                "payload": {
                    "id": "019d096c-895b-78c3-9f34-b5dabf10e089",
                    "cwd": "/home/silas/work",
                    "originator": "codex_vscode",
                    "cli_version": "0.116.0-alpha.10",
                    "source": "vscode",
                    "model_provider": "openai",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ingest"
        body = json.loads(request.content.decode("utf-8"))
        calls.append(body)
        return httpx.Response(200, json={"ids": ["1"] * len(body["logs"])})

    real_client = httpx.Client

    class MockClient:
        def __init__(self, **_: object) -> None:
            self._client = real_client(transport=httpx.MockTransport(handler), base_url="http://test")

        def post(self, *args, **kwargs):
            return self._client.post(*args, **kwargs)

        def close(self) -> None:
            self._client.close()

    monkeypatch.setattr("llmh_client.__main__.httpx.Client", MockClient)

    totals = run_scan(
        ScanConfig(
            api_url="http://test",
            token="token",
            source_name="archive-prod",
            hostname="archive-prod",
            scan_path=tmp_path,
            batch_size=10,
            raw_payload_max_bytes=65536,
            request_target_bytes=512 * 1024,
            dry_run=False,
            tags=["imported"],
        )
    )

    assert totals["files"] == 2
    assert totals["lines"] == 2
    assert totals["uploaded"] == 2
    assert len(calls) == 1
    payload = calls[0]["logs"]
    assert {item["tool"] for item in payload} == {"claude-code", "codex"}


def test_run_scan_splits_and_retries_batches_after_413(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "185.237.218.186_8080"
    nested_root = source_dir / "185.237.218.186:8080"
    project_file = source_dir / "projects" / "-root" / "session.jsonl"
    project_file.parent.mkdir(parents=True)
    nested_root.mkdir(parents=True)
    project_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "user",
                        "message": {"role": "user", "content": "one"},
                        "sessionId": "sess-1",
                        "timestamp": "2026-04-24T16:02:53.261Z",
                    }
                ),
                json.dumps(
                    {
                        "type": "user",
                        "message": {"role": "user", "content": "two"},
                        "sessionId": "sess-1",
                        "timestamp": "2026-04-24T16:02:54.261Z",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        size = len(body["logs"])
        batch_sizes.append(size)
        if size > 1:
            return httpx.Response(413, json={"detail": "too large"}, request=request)
        return httpx.Response(202, json={"ids": ["1"]}, request=request)

    real_client = httpx.Client

    class MockClient:
        def __init__(self, **_: object) -> None:
            self._client = real_client(transport=httpx.MockTransport(handler), base_url="http://test")

        def post(self, *args, **kwargs):
            return self._client.post(*args, **kwargs)

        def close(self) -> None:
            self._client.close()

    monkeypatch.setattr("llmh_client.__main__.httpx.Client", MockClient)

    totals = run_scan(
        ScanConfig(
            api_url="http://test",
            token="token",
            source_name="archive-prod",
            hostname="archive-prod",
            scan_path=nested_root,
            batch_size=10,
            raw_payload_max_bytes=65536,
            request_target_bytes=512 * 1024,
            dry_run=False,
            tags=["imported", "claude-archive"],
        )
    )

    assert totals["uploaded"] == 2
    assert batch_sizes == [2, 1, 1]
