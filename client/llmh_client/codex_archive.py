from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .claude_archive import (
    ClaudeSourceSpec as ArchiveSourceSpec,
    compact_value,
    find_source_dir,
    limit_text,
    parse_source_dir,
    strip_unsafe_text,
    summarize_text,
)

CODEX_IMPORT_TOOL = "codex"
CODEX_DEFAULT_TAGS = ("imported", "codex-archive")
CODEX_RECORD_TYPES = {"session_meta", "event_msg", "response_item", "turn_context"}
CODEX_FILENAME_PATTERN = re.compile(
    r"^rollout-(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})-(?P<sid>[0-9a-f-]{36})$"
)
EXIT_CODE_PATTERN = re.compile(r"Process exited with code (\d+)")


def resolve_scan_root(scan_path: Path) -> tuple[Path, ArchiveSourceSpec | None]:
    resolved = scan_path.expanduser().resolve()
    source_dir = find_source_dir(resolved)
    if source_dir is None:
        return resolved, None
    return source_dir, parse_source_dir(source_dir)


def looks_like_codex_record(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    return record.get("type") in CODEX_RECORD_TYPES and "payload" in record


def is_codex_session_file(path: Path) -> bool:
    if path.suffix != ".jsonl":
        return False
    if not path.name.startswith("rollout-"):
        return False
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                return looks_like_codex_record(json.loads(line))
    except (OSError, json.JSONDecodeError):
        return False
    return False


def narrow_codex_root(root: Path) -> Path:
    """Trim a scan path down to the deepest sensible codex sessions root.

    Avoids walking large unrelated trees (build artifacts, model checkpoints,
    git working copies) when the user passes a parent directory.
    """
    if root.name == ".codex" and (root / "sessions").is_dir():
        return root / "sessions"
    if (root / ".codex" / "sessions").is_dir():
        return root / ".codex" / "sessions"
    return root


def iter_session_files(root: Path) -> list[Path]:
    base = narrow_codex_root(root)
    files: list[Path] = []
    for path in base.rglob("rollout-*.jsonl"):
        if is_codex_session_file(path):
            files.append(path)
    return sorted(files)


def session_id_from_path(path: Path) -> str:
    match = CODEX_FILENAME_PATTERN.match(path.stem)
    if match:
        return match.group("sid")
    return path.stem


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def resolve_sender(record: dict[str, Any]) -> str:
    record_type = record.get("type")
    payload = as_dict(record.get("payload"))
    payload_type = payload.get("type")

    if record_type == "event_msg":
        if payload_type == "user_message":
            return "user"
        if payload_type == "agent_message":
            return "assistant"
        return "system"
    if record_type == "response_item":
        if payload_type == "message":
            role = payload.get("role")
            if role == "user":
                return "user"
            if role == "assistant":
                return "assistant"
            return "system"
        if payload_type == "reasoning":
            return "assistant"
        if payload_type == "function_call":
            return "assistant"
        if payload_type == "function_call_output":
            return "tool_result"
        return "system"
    return "system"


def resolve_level(record: dict[str, Any], sender: str) -> str:
    record_type = record.get("type")
    payload = as_dict(record.get("payload"))
    payload_type = payload.get("type")

    if payload.get("error") or record.get("error"):
        return "error"
    if record_type == "response_item" and payload_type == "function_call_output":
        output = payload.get("output")
        if isinstance(output, str):
            match = EXIT_CODE_PATTERN.search(output)
            if match and match.group(1) != "0":
                return "warn"
    if record_type == "event_msg" and payload_type == "stream_error":
        return "error"
    if record_type == "session_meta":
        return "debug"
    if record_type == "turn_context":
        return "debug"
    if record_type == "event_msg" and payload_type in {"task_started", "task_complete", "token_count"}:
        return "debug"
    if record_type == "response_item" and payload_type == "reasoning":
        return "debug"
    if record_type == "response_item" and payload_type == "message" and payload.get("role") == "developer":
        return "debug"
    return "info"


def _extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"text", "input_text", "output_text"}:
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
        elif item_type == "summary_text":
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
    return "\n\n".join(parts)


def extract_content_text(record: dict[str, Any]) -> str:
    record_type = record.get("type")
    payload = as_dict(record.get("payload"))
    payload_type = payload.get("type")

    if record_type == "session_meta":
        cwd = payload.get("cwd")
        source = payload.get("source") or payload.get("originator") or payload.get("model_provider")
        bits = [f"session start"]
        if cwd:
            bits.append(f"cwd={cwd}")
        if source:
            bits.append(f"via {source}")
        return limit_text(" ".join(bits))
    if record_type == "event_msg":
        if payload_type == "user_message":
            message = payload.get("message")
            if isinstance(message, str):
                return limit_text(message)
        if payload_type == "agent_message":
            message = payload.get("message")
            if isinstance(message, str):
                return limit_text(message)
        if payload_type == "task_complete":
            last_msg = payload.get("last_agent_message")
            if isinstance(last_msg, str):
                return limit_text(last_msg)
        if payload_type == "token_count":
            usage = as_dict(payload.get("info")).get("total_token_usage")
            if isinstance(usage, dict):
                total = usage.get("total_tokens")
                return f"tokens: total={total}"
        if payload_type == "task_started":
            return f"task started: {payload.get('turn_id', '')}".strip()
        return ""
    if record_type == "response_item":
        if payload_type == "message":
            text = _extract_text_from_content(payload.get("content"))
            if text:
                return limit_text(text)
        if payload_type == "reasoning":
            summary = payload.get("summary")
            if isinstance(summary, list):
                text = _extract_text_from_content(summary)
                if text:
                    return limit_text(text)
            content_text = _extract_text_from_content(payload.get("content"))
            if content_text:
                return limit_text(content_text)
            if payload.get("encrypted_content"):
                return ""
            return ""
        if payload_type == "function_call":
            name = payload.get("name", "tool")
            args = payload.get("arguments")
            details = ""
            if isinstance(args, str):
                try:
                    parsed = json.loads(args)
                    if isinstance(parsed, dict):
                        details = parsed.get("cmd") or parsed.get("command") or parsed.get("path") or parsed.get("file_path") or ""
                except (TypeError, ValueError):
                    details = args
            return limit_text(f"[tool_use:{name}] {details}".strip())
        if payload_type == "function_call_output":
            output = payload.get("output")
            if isinstance(output, str):
                return limit_text(output)
        return ""
    if record_type == "turn_context":
        model = payload.get("model")
        cwd = payload.get("cwd")
        return f"turn context: model={model} cwd={cwd}"
    return ""


def summarize_message(record: dict[str, Any], sender: str) -> str:
    record_type = record.get("type")
    payload = as_dict(record.get("payload"))
    payload_type = payload.get("type")

    if record_type == "session_meta":
        return f"session_meta: {payload.get('originator', payload.get('source', 'codex'))} cwd={payload.get('cwd', '?')}"
    if record_type == "turn_context":
        return f"turn_context: {payload.get('model', '?')} cwd={payload.get('cwd', '?')}"
    if record_type == "event_msg" and payload_type == "task_started":
        return f"task_started: turn={payload.get('turn_id', '?')}"
    if record_type == "event_msg" and payload_type == "task_complete":
        last = payload.get("last_agent_message")
        if isinstance(last, str) and last:
            return f"task_complete: {summarize_text(last)}"
        return f"task_complete: turn={payload.get('turn_id', '?')}"
    if record_type == "event_msg" and payload_type == "token_count":
        usage = as_dict(payload.get("info")).get("total_token_usage")
        total = usage.get("total_tokens") if isinstance(usage, dict) else "?"
        return f"token_count: total={total}"

    content_text = extract_content_text(record)
    if content_text:
        return f"{sender}: {summarize_text(content_text)}"
    if payload_type:
        return f"{sender}: {record_type}/{payload_type}"
    return f"{sender}: {record_type or 'event'}"


def parse_timestamp(record: dict[str, Any], fallback: datetime) -> datetime:
    value = record.get("timestamp")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            pass
    payload = as_dict(record.get("payload"))
    payload_ts = payload.get("timestamp")
    if isinstance(payload_ts, str):
        try:
            return datetime.fromisoformat(payload_ts.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            pass
    return fallback


def build_tags(record: dict[str, Any], sender: str, payload_type: str | None) -> list[str]:
    tags = [
        "imported",
        "codex-archive",
        f"sender:{sender}",
        f"record:{record.get('type', 'unknown')}",
    ]
    if payload_type:
        tags.append(f"payload:{payload_type}")
    return tags


def _resolve_session_meta(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("type") != "session_meta":
        return {}
    return as_dict(record.get("payload"))


def build_raw_payload(
    record: dict[str, Any],
    *,
    source: ArchiveSourceSpec | None,
    session_file: Path,
    session_file_relative: str | None = None,
    line_number: int,
    sender: str,
    session_id: str,
) -> dict[str, Any]:
    payload = as_dict(record.get("payload"))
    payload_type = payload.get("type")
    meta = _resolve_session_meta(record)

    source_name = source.source_name if source is not None else None
    source_ip = source.ip_address if source is not None else None
    source_port = source.port if source is not None else None
    relative_file = session_file_relative or str(session_file)
    if source is not None:
        if session_file_relative is None:
            try:
                relative_file = str(session_file.relative_to(source.source_dir))
            except ValueError:
                relative_file = str(session_file)

    tool_call_id = None
    tool_call_name = None
    tool_call_args: Any = None
    tool_call_output = None
    if record.get("type") == "response_item":
        if payload_type == "function_call":
            tool_call_id = payload.get("call_id")
            tool_call_name = payload.get("name")
            args = payload.get("arguments")
            if isinstance(args, str):
                try:
                    tool_call_args = compact_value(json.loads(args))
                except (TypeError, ValueError):
                    tool_call_args = limit_text(args)
            else:
                tool_call_args = compact_value(args)
        elif payload_type == "function_call_output":
            tool_call_id = payload.get("call_id")
            output = payload.get("output")
            tool_call_output = limit_text(output) if isinstance(output, str) else compact_value(output)

    cwd = meta.get("cwd") or payload.get("cwd")
    model = meta.get("model") or payload.get("model")
    originator = meta.get("originator")
    cli_version = meta.get("cli_version")
    source_app = meta.get("source")

    return {
        "import": {
            "format": "codex-rollout-jsonl",
            "source_name": source_name,
            "source_ip": source_ip,
            "source_port": source_port,
            "session_file": relative_file,
            "line_number": line_number,
        },
        "sender": sender,
        "record_type": record.get("type"),
        "payload_type": payload_type,
        "session_id": session_id,
        "turn_id": payload.get("turn_id"),
        "cwd": cwd,
        "model": model,
        "originator": originator,
        "cli_version": cli_version,
        "source_app": source_app,
        "model_provider": meta.get("model_provider"),
        "message_role": payload.get("role") if payload_type == "message" else None,
        "tool_call_id": tool_call_id,
        "tool_call_name": tool_call_name,
        "tool_input": tool_call_args,
        "tool_result": tool_call_output,
        "content_text": extract_content_text(record),
        "record": compact_value(record),
    }
