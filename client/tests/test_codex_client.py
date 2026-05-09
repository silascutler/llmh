from __future__ import annotations

import json
from pathlib import Path

import httpx

from llmh_client.__main__ import CODEX_PARSER, ScanConfig, run_scan
from llmh_client.codex_archive import (
    extract_content_text,
    is_codex_session_file,
    iter_session_files,
    resolve_level,
    resolve_sender,
    session_id_from_path,
    summarize_message,
)


SAMPLE_USER = {
    "timestamp": "2026-03-20T04:07:01.371Z",
    "type": "event_msg",
    "payload": {"type": "user_message", "message": "increase bet size to $10", "images": [], "local_images": []},
}

SAMPLE_AGENT = {
    "timestamp": "2026-03-20T04:07:06.256Z",
    "type": "event_msg",
    "payload": {"type": "agent_message", "message": "checking project config", "phase": "commentary"},
}

SAMPLE_FUNCTION_CALL = {
    "timestamp": "2026-03-20T04:07:06.259Z",
    "type": "response_item",
    "payload": {
        "type": "function_call",
        "name": "exec_command",
        "arguments": "{\"cmd\":\"pwd\",\"workdir\":\"/work\"}",
        "call_id": "call_abc",
    },
}

SAMPLE_FUNCTION_OUTPUT_FAIL = {
    "timestamp": "2026-03-20T04:07:06.315Z",
    "type": "response_item",
    "payload": {
        "type": "function_call_output",
        "call_id": "call_abc",
        "output": "Command: bash -lc make\nProcess exited with code 2\nOutput:\nbuild failed\n",
    },
}

SAMPLE_SESSION_META = {
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

SAMPLE_RESPONSE_MESSAGE = {
    "timestamp": "2026-03-20T04:07:09.000Z",
    "type": "response_item",
    "payload": {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "Final answer."}],
    },
}


def test_session_id_from_path_extracts_uuid_suffix() -> None:
    path = Path("rollout-2026-03-20T00-06-41-019d096c-895b-78c3-9f34-b5dabf10e089.jsonl")
    assert session_id_from_path(path) == "019d096c-895b-78c3-9f34-b5dabf10e089"


def test_resolve_sender_maps_event_and_response_records() -> None:
    assert resolve_sender(SAMPLE_USER) == "user"
    assert resolve_sender(SAMPLE_AGENT) == "assistant"
    assert resolve_sender(SAMPLE_FUNCTION_CALL) == "assistant"
    assert resolve_sender(SAMPLE_FUNCTION_OUTPUT_FAIL) == "tool_result"
    assert resolve_sender(SAMPLE_SESSION_META) == "system"
    assert resolve_sender(SAMPLE_RESPONSE_MESSAGE) == "assistant"


def test_resolve_level_flags_nonzero_exit_as_warn() -> None:
    assert resolve_level(SAMPLE_FUNCTION_OUTPUT_FAIL, "tool_result") == "warn"
    success_output = {
        "type": "response_item",
        "payload": {"type": "function_call_output", "output": "Process exited with code 0\nok\n"},
    }
    assert resolve_level(success_output, "tool_result") == "info"


def test_resolve_level_marks_meta_and_token_count_debug() -> None:
    assert resolve_level(SAMPLE_SESSION_META, "system") == "debug"
    token_count = {"type": "event_msg", "payload": {"type": "token_count", "info": {}}}
    assert resolve_level(token_count, "system") == "debug"


def test_extract_content_text_handles_input_and_output_text() -> None:
    assert extract_content_text(SAMPLE_USER) == "increase bet size to $10"
    assert extract_content_text(SAMPLE_AGENT) == "checking project config"
    assert extract_content_text(SAMPLE_RESPONSE_MESSAGE) == "Final answer."
    assert extract_content_text(SAMPLE_FUNCTION_CALL).startswith("[tool_use:exec_command]")


def test_summarize_message_uses_session_meta_originator() -> None:
    summary = summarize_message(SAMPLE_SESSION_META, "system")
    assert "codex_vscode" in summary
    assert "/home/silas/work" in summary


def test_is_codex_session_file_filters_by_record_shape(tmp_path: Path) -> None:
    good = tmp_path / "rollout-2026-03-20T00-00-00-019d096c-895b-78c3-9f34-b5dabf10e089.jsonl"
    bad = tmp_path / "rollout-other.jsonl"
    not_rollout = tmp_path / "session.jsonl"
    good.write_text(json.dumps(SAMPLE_SESSION_META) + "\n", encoding="utf-8")
    bad.write_text(json.dumps({"foo": "bar"}) + "\n", encoding="utf-8")
    not_rollout.write_text(json.dumps(SAMPLE_SESSION_META) + "\n", encoding="utf-8")

    assert is_codex_session_file(good) is True
    assert is_codex_session_file(bad) is False
    assert is_codex_session_file(not_rollout) is False
    assert iter_session_files(tmp_path) == [good]


def test_run_scan_uploads_codex_logs(tmp_path: Path, monkeypatch) -> None:
    sessions_dir = tmp_path / ".codex" / "sessions" / "2026" / "03" / "20"
    sessions_dir.mkdir(parents=True)
    rollout = sessions_dir / "rollout-2026-03-20T00-06-41-019d096c-895b-78c3-9f34-b5dabf10e089.jsonl"
    rollout.write_text(
        "\n".join(
            [
                json.dumps(SAMPLE_SESSION_META),
                json.dumps(SAMPLE_USER),
                json.dumps(SAMPLE_FUNCTION_CALL),
                json.dumps(SAMPLE_FUNCTION_OUTPUT_FAIL),
                json.dumps(SAMPLE_AGENT),
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

    config = ScanConfig(
        api_url="http://test",
        token="token",
        source_name="codex-laptop",
        hostname="codex-laptop",
        scan_path=tmp_path / ".codex",
        batch_size=10,
        raw_payload_max_bytes=65536,
        request_target_bytes=512 * 1024,
        dry_run=False,
        tags=["imported", "codex-archive"],
    )

    totals = run_scan(config, CODEX_PARSER)

    assert totals["files"] == 1
    assert totals["lines"] == 5
    assert totals["uploaded"] == 5
    assert totals["skipped"] == 0
    assert len(calls) == 1
    payload = calls[0]["logs"]
    assert {p["tool"] for p in payload} == {"codex"}
    assert all(p["session_id"] == "019d096c-895b-78c3-9f34-b5dabf10e089" for p in payload)
    by_sender = {p["raw"]["sender"]: p for p in payload}
    assert by_sender["user"]["raw"]["content_text"] == "increase bet size to $10"
    assert by_sender["assistant"]["raw"]["content_text"] == "checking project config"
    assert by_sender["tool_result"]["level"] == "warn"
    assert by_sender["assistant"] is not None  # agent_message present
    fc = next(p for p in payload if p["raw"]["payload_type"] == "function_call")
    assert fc["raw"]["tool_call_name"] == "exec_command"
    assert fc["raw"]["tool_call_id"] == "call_abc"
    assert fc["raw"]["tool_input"] == {"cmd": "pwd", "workdir": "/work"}
    assert payload[0]["source_key"]["name"] == "codex-laptop"
    assert payload[0]["source_key"]["ip_address"] is None
    assert payload[0]["source_key"]["port"] is None
