from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from llmh.utils.claude_import import (
    build_log_ingest,
    extract_content_text,
    find_source_dir,
    iter_project_files,
    parse_source_dir,
    resolve_level,
    summarize_message,
)


def test_parse_source_dir_extracts_ip_and_port() -> None:
    spec = parse_source_dir(Path("/tmp/import/165.22.184.26_8888"))

    assert spec.source_name == "165.22.184.26_8888"
    assert spec.ip_address == "165.22.184.26"
    assert spec.port == 8888


def test_find_source_dir_handles_nested_projects_tree() -> None:
    path = Path("/tmp/import/204.152.192.16_8000/homunculus/projects/94a6b4475803/observations.jsonl")

    assert find_source_dir(path) == Path("/tmp/import/204.152.192.16_8000")


def test_build_log_ingest_preserves_session_project_and_sender_context() -> None:
    record = {
        "type": "user",
        "message": {"role": "user", "content": "investigate the service failure"},
        "uuid": "abc",
        "timestamp": "2026-04-24T16:02:53.261Z",
        "cwd": "/root/app",
        "sessionId": "session-123",
        "version": "2.1.119",
        "gitBranch": "main",
    }

    payload = build_log_ingest(
        record,
        source_id=str(uuid.uuid4()),
        source=parse_source_dir(Path("/tmp/import/161.97.107.130_8080")),
        project_file=Path("/tmp/import/161.97.107.130_8080/projects/-root/app-session.jsonl"),
        line_number=7,
        fallback_time=datetime(2026, 4, 24, 16, 2, 53, tzinfo=timezone.utc),
    )

    assert payload.session_id == "session-123"
    assert payload.tags == ["imported", "claude-archive", "sender:user", "record:user", "project:-root"]
    assert payload.message.startswith("user:")
    assert payload.raw["sender"] == "user"
    assert payload.raw["cwd"] == "/root/app"
    assert payload.raw["project_name"] == "app"
    assert payload.raw["import"]["line_number"] == 7


def test_iter_project_files_includes_nested_projects_tree(tmp_path: Path) -> None:
    direct = tmp_path / "161.97.107.130_8080" / "projects" / "-root" / "session.jsonl"
    nested = tmp_path / "204.152.192.16_8000" / "homunculus" / "projects" / "94a6b4475803" / "observations.jsonl"
    ignored = tmp_path / "204.152.192.16_8000" / "sessions" / "ignored.jsonl"
    direct.parent.mkdir(parents=True)
    nested.parent.mkdir(parents=True)
    ignored.parent.mkdir(parents=True)
    direct.write_text("{}", encoding="utf-8")
    nested.write_text("{}", encoding="utf-8")
    ignored.write_text("{}", encoding="utf-8")

    assert iter_project_files(tmp_path) == [direct, nested]


def test_resolve_level_marks_api_errors_as_error() -> None:
    record = {
        "type": "assistant",
        "error": "authentication_failed",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "Please run /login"}]},
    }

    assert resolve_level(record, "assistant") == "error"


def test_resolve_level_marks_string_tool_errors_as_warn() -> None:
    record = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "content": "Request failed with status code 402", "is_error": True}],
        },
        "toolUseResult": "Error: Request failed with status code 402",
    }

    assert resolve_level(record, "tool_result") == "warn"


def test_build_log_ingest_strips_null_bytes_from_text_fields() -> None:
    record = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "content": "bad\x00output"}],
        },
        "toolUseResult": {"stderr": "oops\x00"},
        "timestamp": "2026-04-24T16:02:53.261Z",
    }

    payload = build_log_ingest(
        record,
        source_id=str(uuid.uuid4()),
        source=parse_source_dir(Path("/tmp/import/161.97.107.130_8080")),
        project_file=Path("/tmp/import/161.97.107.130_8080/projects/-root/app-session.jsonl"),
        line_number=9,
        fallback_time=datetime(2026, 4, 24, 16, 2, 53, tzinfo=timezone.utc),
    )

    assert "\x00" not in payload.message
    assert "\x00" not in payload.raw["content_text"]
    assert "\x00" not in payload.raw["tool_result"]["stderr"]


def test_summary_records_use_summary_text_for_message_and_content() -> None:
    record = {
        "type": "summary",
        "summary": 'API Error: 401 {"type":"error"} · Please run /login',
    }

    assert extract_content_text(record) == 'API Error: 401 {"type":"error"} · Please run /login'
    assert summarize_message(record, "system").startswith("system: API Error: 401")


def test_assistant_thinking_falls_back_when_no_text_content_exists() -> None:
    record = {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {
                    "type": "thinking",
                    "thinking": "Good, the downloads are progressing and the transfer is still active.",
                }
            ],
        },
    }

    assert extract_content_text(record) == "Good, the downloads are progressing and the transfer is still active."
    assert summarize_message(record, "assistant").startswith("assistant: Good, the downloads are progressing")
