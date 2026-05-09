from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llmh.schemas.log import LogIngest

CLAUDE_IMPORT_TOOL = "claude-code"
MAX_MESSAGE_LENGTH = 280
MAX_CONTENT_TEXT = 20000
MAX_GENERIC_STRING = 2000
MAX_LIST_ITEMS = 24
MAX_DEPTH = 5
SOURCE_DIR_PATTERN = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}_\d+$")


@dataclass(slots=True)
class ClaudeSourceSpec:
    source_dir: Path
    source_name: str
    ip_address: str
    port: int


def parse_source_dir(path: Path) -> ClaudeSourceSpec:
    name = path.name
    ip_address, port_text = name.rsplit("_", 1)
    return ClaudeSourceSpec(source_dir=path, source_name=name, ip_address=ip_address, port=int(port_text))


def iter_project_files(root: Path) -> list[Path]:
    project_files: list[Path] = []
    for path in root.rglob("*.jsonl"):
        if "projects" not in path.parts:
            continue
        if find_source_dir(path) is None:
            continue
        project_files.append(path)
    return sorted(project_files)


def find_source_dir(path: Path) -> Path | None:
    for parent in path.parents:
        if SOURCE_DIR_PATTERN.match(parent.name):
            return parent
    return None


def summarize_text(value: str, limit: int = MAX_MESSAGE_LENGTH) -> str:
    compact = " ".join(strip_unsafe_text(value).split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1].rstrip()}…"


def limit_text(value: str, limit: int = MAX_CONTENT_TEXT) -> str:
    value = strip_unsafe_text(value)
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"


def strip_unsafe_text(value: str) -> str:
    return value.replace("\x00", "")


def compact_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= MAX_DEPTH:
        return "<truncated-depth>"
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return limit_text(value, MAX_GENERIC_STRING)
    if isinstance(value, list):
        clipped = [compact_value(item, depth=depth + 1) for item in value[:MAX_LIST_ITEMS]]
        if len(value) > MAX_LIST_ITEMS:
            clipped.append(f"<truncated:{len(value) - MAX_LIST_ITEMS} more>")
        return clipped
    if isinstance(value, dict):
        return {str(key): compact_value(item, depth=depth + 1) for key, item in value.items()}
    return repr(value)


def as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def resolve_sender(record: dict[str, Any]) -> str:
    if record.get("type") == "user":
        content = as_dict(record.get("message")).get("content")
        if isinstance(content, list) and all(isinstance(item, dict) and item.get("type") == "tool_result" for item in content):
            return "tool_result"
        return "user"
    if record.get("type") == "assistant":
        return "assistant"
    return "system"


def resolve_level(record: dict[str, Any], sender: str) -> str:
    record_type = record.get("type")
    if record.get("error") or record.get("isApiErrorMessage"):
        return "error"
    if sender == "tool_result":
        tool_result = record.get("toolUseResult")
        content = as_dict(record.get("message")).get("content")
        if isinstance(tool_result, dict) and (tool_result.get("interrupted") or tool_result.get("stderr")):
            return "warn"
        if isinstance(tool_result, str) and tool_result.strip():
            return "warn" if tool_result.lstrip().lower().startswith("error:") else "info"
        if isinstance(content, list) and any(isinstance(item, dict) and item.get("is_error") for item in content):
            return "warn"
    if record_type in {"permission-mode", "last-prompt", "file-history-snapshot"}:
        return "debug"
    if record_type == "attachment":
        attachment_type = as_dict(record.get("attachment")).get("type")
        if attachment_type in {"hook_success", "deferred_tools_delta", "skill_listing"}:
            return "debug"
    return "info"


def extract_content_text(record: dict[str, Any]) -> str:
    if record.get("type") == "summary":
        summary = record.get("summary")
        if isinstance(summary, str) and summary:
            return limit_text(summary)
    message = as_dict(record.get("message"))
    content = message.get("content")
    if isinstance(content, str):
        return limit_text(content)
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    thinking_parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "text":
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
        elif item_type == "thinking":
            thinking = item.get("thinking")
            if isinstance(thinking, str) and thinking:
                thinking_parts.append(thinking)
        elif item_type == "tool_use":
            name = item.get("name", "tool")
            input_value = item.get("input")
            details = ""
            if isinstance(input_value, dict):
                details = input_value.get("description") or input_value.get("activeForm") or input_value.get("command") or input_value.get("file_path") or ""
            parts.append(f"[tool_use:{name}] {details}".strip())
        elif item_type == "tool_result":
            content_value = item.get("content")
            if isinstance(content_value, str):
                parts.append(content_value)
    if parts:
        return limit_text("\n\n".join(part for part in parts if part))
    return limit_text("\n\n".join(part for part in thinking_parts if part))


def summarize_message(record: dict[str, Any], sender: str) -> str:
    record_type = record.get("type")
    if record_type == "summary":
        summary = record.get("summary")
        if isinstance(summary, str) and summary:
            return f"{sender}: {summarize_text(summary)}"
        return "system: summary"
    if record_type == "permission-mode":
        return f"permission mode: {record.get('permissionMode', 'unknown')}"
    if record_type == "last-prompt":
        return f"last prompt: {summarize_text(str(record.get('lastPrompt', '')))}"
    if record_type == "file-history-snapshot":
        return f"file history snapshot: {record.get('messageId', 'unknown')}"
    if record_type == "attachment":
        attachment = as_dict(record.get("attachment"))
        attachment_type = attachment.get("type", "attachment")
        if attachment_type == "hook_success":
            hook_name = attachment.get("hookName", "hook")
            exit_code = attachment.get("exitCode", "?")
            return f"hook {hook_name} exited {exit_code}"
        if attachment_type == "deferred_tools_delta":
            added = attachment.get("addedNames", [])
            return f"tools updated: {len(added) if isinstance(added, list) else 0} added"
        if attachment_type == "skill_listing":
            return f"skill listing: {attachment.get('skillCount', 'unknown')} skills"
        return f"attachment: {attachment_type}"

    content_text = extract_content_text(record)
    if content_text:
        return f"{sender}: {summarize_text(content_text)}"
    if record.get("error"):
        return f"{sender}: {record['error']}"
    return f"{sender}: {record_type or 'event'}"


def build_raw_payload(
    record: dict[str, Any],
    *,
    source: ClaudeSourceSpec,
    project_file: Path,
    line_number: int,
    sender: str,
) -> dict[str, Any]:
    message = as_dict(record.get("message"))
    attachment = as_dict(record.get("attachment"))
    tool_result = record.get("toolUseResult")
    cwd = record.get("cwd")

    return {
        "import": {
            "format": "claude-project-jsonl",
            "source_name": source.source_name,
            "source_ip": source.ip_address,
            "source_port": source.port,
            "project_folder": project_file.parent.name,
            "project_file": str(project_file.relative_to(source.source_dir)),
            "session_file": project_file.name,
            "line_number": line_number,
        },
        "sender": sender,
        "record_type": record.get("type"),
        "attachment_type": attachment.get("type"),
        "session_id": record.get("sessionId"),
        "uuid": record.get("uuid"),
        "parent_uuid": record.get("parentUuid"),
        "prompt_id": record.get("promptId"),
        "cwd": cwd,
        "project_name": Path(cwd).name if isinstance(cwd, str) and cwd else project_file.parent.name,
        "version": record.get("version"),
        "git_branch": record.get("gitBranch"),
        "entrypoint": record.get("entrypoint"),
        "user_type": record.get("userType"),
        "permission_mode": record.get("permissionMode"),
        "slug": record.get("slug"),
        "model": message.get("model"),
        "message_role": message.get("role"),
        "request_id": record.get("requestId"),
        "error": record.get("error"),
        "stop_reason": message.get("stop_reason"),
        "content_text": extract_content_text(record),
        "tool_input": compact_value(next((item.get("input") for item in message.get("content", []) if isinstance(item, dict) and item.get("type") == "tool_use"), None)),
        "tool_result": compact_value(tool_result) if tool_result is not None else None,
        "record": compact_value(record),
    }


def parse_timestamp(record: dict[str, Any], fallback: datetime) -> datetime:
    value = record.get("timestamp")
    if value is None and isinstance(record.get("snapshot"), dict):
        value = record["snapshot"].get("timestamp")
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return fallback


def build_tags(record: dict[str, Any], sender: str, project_file: Path) -> list[str]:
    tags = [
        "imported",
        "claude-archive",
        f"sender:{sender}",
        f"record:{record.get('type', 'unknown')}",
        f"project:{project_file.parent.name}",
    ]
    attachment_type = as_dict(record.get("attachment")).get("type")
    if attachment_type:
        tags.append(f"attachment:{attachment_type}")
    return tags


def build_log_ingest(
    record: dict[str, Any],
    *,
    source_id: str,
    source: ClaudeSourceSpec,
    project_file: Path,
    line_number: int,
    fallback_time: datetime,
) -> LogIngest:
    sender = resolve_sender(record)
    raw = build_raw_payload(record, source=source, project_file=project_file, line_number=line_number, sender=sender)
    return LogIngest.model_validate(
        {
            "source_id": source_id,
            "tool": CLAUDE_IMPORT_TOOL,
            "session_id": record.get("sessionId") or project_file.stem,
            "idempotency_key": f"claude-import:{source.source_name}:{project_file.parent.name}:{project_file.stem}:{line_number}",
            "level": resolve_level(record, sender),
            "message": summarize_message(record, sender),
            "raw": raw,
            "tags": build_tags(record, sender, project_file),
            "occurred_at": parse_timestamp(record, fallback_time).isoformat(),
        }
    )
