from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
import typer


def _log_progress(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)

from . import claude_archive, codex_archive
from .claude_archive import ClaudeSourceSpec as ArchiveSourceSpec
from .claude_archive import is_claude_project_file
from .codex_archive import is_codex_session_file

app = typer.Typer(
    add_completion=False,
    help=(
        "Ship Claude and Codex archive logs to llmh.\n\n"
        "Use `ship` for normal usage: it auto-detects Claude project JSONL files and Codex rollout JSONL files "
        "from the scan path, then uploads them in batches. Use `ship-claude` or `ship-codex` only when you want "
        "to force a specific parser.\n\n"
        "Examples:\n"
        "  llmh-client ship --source-name laptop --scan-path ~/.codex/sessions\n"
        "  llmh-client ship --source-name prod-archive --scan-path /archives/185.237.218.186_8080\n"
        "  llmh-client ship-codex --source-name laptop --scan-path ~/.codex/sessions"
    ),
)
DEFAULT_BATCH_SIZE = 100
DEFAULT_RAW_PAYLOAD_MAX_BYTES = 65536
DEFAULT_REQUEST_TARGET_BYTES = 512 * 1024
DEFAULT_REQUEST_TIMEOUT_S = 300.0


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    source_name: str | None = typer.Option(None, help="Logical source name to create/use in llmh."),
    scan_path: Path = typer.Option(
        Path("~/.codex/sessions").expanduser(),
        exists=False,
        file_okay=True,
        dir_okay=True,
        help="Path to scan for archive logs. Claude and Codex files are detected automatically.",
    ),
    api_url: str = typer.Option(default_factory=lambda: os.getenv("LLMH_API_URL", ""), help="API base URL."),
    token: str = typer.Option(default_factory=lambda: os.getenv("LLMH_INGEST_TOKEN", ""), help="Bearer ingest token."),
    hostname: str | None = typer.Option(default=None, help="Optional hostname override; defaults to source name."),
    batch_size: int = typer.Option(DEFAULT_BATCH_SIZE, min=1, max=1000, help="Number of log entries per upload batch."),
    raw_payload_max_bytes: int = typer.Option(
        DEFAULT_RAW_PAYLOAD_MAX_BYTES,
        min=1024,
        help="Maximum raw payload size to target per uploaded log.",
    ),
    request_target_bytes: int = typer.Option(
        DEFAULT_REQUEST_TARGET_BYTES,
        min=16384,
        help="Target maximum JSON request size per upload batch.",
    ),
    tag: list[str] = typer.Option(default_factory=list, help="Extra tag applied to every uploaded log."),
    request_timeout_s: float = typer.Option(
        DEFAULT_REQUEST_TIMEOUT_S,
        "--request-timeout",
        min=5.0,
        help="HTTP read/write timeout per upload request, in seconds.",
    ),
    dry_run: bool = typer.Option(default=False, help="Print payloads instead of uploading."),
) -> None:
    """Standalone archive shipping client."""
    if ctx.invoked_subcommand is not None:
        return
    if source_name is None:
        raise typer.BadParameter("--source-name is required when running without a subcommand")
    config = _build_config(
        api_url=api_url,
        token=token,
        source_name=source_name,
        hostname=hostname,
        scan_path=scan_path,
        batch_size=batch_size,
        raw_payload_max_bytes=raw_payload_max_bytes,
        request_target_bytes=request_target_bytes,
        tag=tag,
        dry_run=dry_run,
        request_timeout_s=request_timeout_s,
    )
    totals = run_scan(config)
    print(json.dumps(totals, sort_keys=True))


@dataclass(slots=True)
class ScanConfig:
    api_url: str
    token: str
    source_name: str
    hostname: str
    scan_path: Path
    batch_size: int
    raw_payload_max_bytes: int
    request_target_bytes: int
    dry_run: bool
    tags: list[str]
    request_timeout_s: float = DEFAULT_REQUEST_TIMEOUT_S


@dataclass(slots=True)
class Parser:
    tool: str
    archive_format: str
    idempotency_prefix: str
    resolve_scan_root: Callable[[Path], tuple[Path, ArchiveSourceSpec | None]]
    iter_files: Callable[[Path], list[Path]]
    build_record_fields: Callable[..., dict[str, Any]]


@dataclass(slots=True)
class FileContext:
    project_file: Path
    source_spec: ArchiveSourceSpec | None
    source_key: dict[str, Any]
    fallback_time: datetime
    relative_file: str
    project_folder: str
    session_id: str


@dataclass(slots=True)
class PreparedLog:
    payload: dict[str, Any]
    raw_bytes: int
    request_bytes: int
    truncated: bool


def _claude_build_record_fields(
    *,
    record: dict[str, Any],
    file_context: FileContext,
    line_number: int,
    config: ScanConfig,
) -> dict[str, Any]:
    project_file = file_context.project_file
    sender = claude_archive.resolve_sender(record)
    return {
        "session_id": record.get("sessionId") or project_file.stem,
        "idempotency_key": f"claude-client:{config.source_name}:{project_file.parent.name}:{project_file.stem}:{line_number}",
        "level": claude_archive.resolve_level(record, sender),
        "message": claude_archive.summarize_message(record, sender),
        "raw": claude_archive.build_raw_payload(
            record,
            source=file_context.source_spec,
            project_file=project_file,
            project_file_relative=file_context.relative_file,
            project_folder=file_context.project_folder,
            line_number=line_number,
            sender=sender,
        ),
        "tags": sorted(set(config.tags + claude_archive.build_tags(record, sender, project_file))),
        "occurred_at": claude_archive.parse_timestamp(record, file_context.fallback_time).isoformat(),
    }


def _codex_build_record_fields(
    *,
    record: dict[str, Any],
    file_context: FileContext,
    line_number: int,
    config: ScanConfig,
) -> dict[str, Any]:
    project_file = file_context.project_file
    sender = codex_archive.resolve_sender(record)
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    payload_type = payload.get("type") if isinstance(payload, dict) else None
    session_id = file_context.session_id
    return {
        "session_id": session_id,
        "idempotency_key": f"codex-client:{config.source_name}:{project_file.stem}:{line_number}",
        "level": codex_archive.resolve_level(record, sender),
        "message": codex_archive.summarize_message(record, sender),
        "raw": codex_archive.build_raw_payload(
            record,
            source=file_context.source_spec,
            session_file=project_file,
            session_file_relative=file_context.relative_file,
            line_number=line_number,
            sender=sender,
            session_id=session_id,
        ),
        "tags": sorted(set(config.tags + codex_archive.build_tags(record, sender, payload_type))),
        "occurred_at": codex_archive.parse_timestamp(record, file_context.fallback_time).isoformat(),
    }


CLAUDE_PARSER = Parser(
    tool=claude_archive.CLAUDE_IMPORT_TOOL,
    archive_format="claude-project-jsonl",
    idempotency_prefix="claude-client",
    resolve_scan_root=claude_archive.resolve_scan_root,
    iter_files=claude_archive.iter_project_files,
    build_record_fields=_claude_build_record_fields,
)

CODEX_PARSER = Parser(
    tool=codex_archive.CODEX_IMPORT_TOOL,
    archive_format="codex-rollout-jsonl",
    idempotency_prefix="codex-client",
    resolve_scan_root=codex_archive.resolve_scan_root,
    iter_files=codex_archive.iter_session_files,
    build_record_fields=_codex_build_record_fields,
)


def detect_parser_for_file(path: Path) -> Parser | None:
    if is_codex_session_file(path):
        return CODEX_PARSER
    if is_claude_project_file(path):
        return CLAUDE_PARSER
    return None


def discover_archive_files(scan_path: Path) -> list[tuple[Parser, Path]]:
    resolved = scan_path.expanduser().resolve()
    candidate_roots: list[Path] = [resolved]
    for parser in (CLAUDE_PARSER, CODEX_PARSER):
        root, _ = parser.resolve_scan_root(resolved)
        candidate_roots.append(root)

    discovered: list[tuple[Parser, Path]] = []
    seen: set[Path] = set()
    for root in candidate_roots:
        if root in seen or not root.exists():
            continue
        seen.add(root)
        if root.is_file():
            parser = detect_parser_for_file(root)
            if parser is not None:
                discovered.append((parser, root))
            continue
        for path in root.rglob("*.jsonl"):
            if path in seen:
                continue
            parser = detect_parser_for_file(path)
            if parser is not None:
                discovered.append((parser, path))
                seen.add(path)
    return sorted(discovered, key=lambda item: str(item[1]))


def build_source_key(config: ScanConfig, *, source_ip: str | None, source_port: int | None) -> dict[str, Any]:
    return {
        "name": config.source_name,
        "hostname": config.hostname,
        "ip_address": source_ip,
        "port": source_port,
        "tags": config.tags,
    }


def build_log_payload(
    parser: Parser,
    config: ScanConfig,
    *,
    record: dict[str, Any],
    file_context: FileContext,
    line_number: int,
) -> dict[str, Any]:
    fields = parser.build_record_fields(
        record=record,
        file_context=file_context,
        line_number=line_number,
        config=config,
    )
    return {"source_key": file_context.source_key, "tool": parser.tool, **fields}


def build_file_context(parser: Parser, config: ScanConfig, project_file: Path) -> FileContext:
    _, source_spec = parser.resolve_scan_root(project_file)
    source_key = build_source_key(
        config,
        source_ip=source_spec.ip_address if source_spec is not None else None,
        source_port=source_spec.port if source_spec is not None else None,
    )
    fallback_time = datetime.fromtimestamp(project_file.stat().st_mtime, tz=timezone.utc)

    if parser is CLAUDE_PARSER:
        source_dir = source_spec.source_dir if source_spec is not None else project_file.parents[1]
        relative_file = str(project_file.relative_to(source_dir))
        session_id = project_file.stem
    elif parser is CODEX_PARSER:
        session_id = codex_archive.session_id_from_path(project_file)
        if source_spec is not None:
            try:
                relative_file = str(project_file.relative_to(source_spec.source_dir))
            except ValueError:
                relative_file = str(project_file)
        else:
            relative_file = str(project_file)
    else:
        relative_file = str(project_file)
        session_id = project_file.stem

    return FileContext(
        project_file=project_file,
        source_spec=source_spec,
        source_key=source_key,
        fallback_time=fallback_time,
        relative_file=relative_file,
        project_folder=project_file.parent.name,
        session_id=session_id,
    )


def raw_size_bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload["raw"], separators=(",", ":")).encode("utf-8"))


def payload_size_bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def request_size_bytes(batch: list[dict[str, Any]]) -> int:
    return len(json.dumps({"logs": batch}, separators=(",", ":")).encode("utf-8"))


REQUEST_PREFIX_BYTES = len(b'{"logs":[')
REQUEST_SUFFIX_BYTES = len(b"]}")


def request_size_from_payload_sizes(payload_sizes: list[int]) -> int:
    if not payload_sizes:
        return REQUEST_PREFIX_BYTES + REQUEST_SUFFIX_BYTES
    return REQUEST_PREFIX_BYTES + REQUEST_SUFFIX_BYTES + sum(payload_sizes) + len(payload_sizes) - 1


def prepare_for_upload(payload: dict[str, Any], *, max_raw_bytes: int) -> PreparedLog:
    original_raw_bytes = raw_size_bytes(payload)
    if original_raw_bytes <= max_raw_bytes:
        return PreparedLog(
            payload=payload,
            raw_bytes=original_raw_bytes,
            request_bytes=payload_size_bytes(payload),
            truncated=False,
        )

    shrunk = json.loads(json.dumps(payload))
    raw = shrunk["raw"]
    raw["truncated"] = True
    raw["truncation_reason"] = "raw payload too large"

    if raw.get("record") is not None:
        raw["record"] = {"truncated": True, "reason": "raw payload too large"}
    if raw.get("tool_result") is not None:
        raw["tool_result"] = "<truncated:tool_result>"
    if raw.get("tool_input") is not None:
        raw["tool_input"] = "<truncated:tool_input>"
    shrunk_raw_bytes = raw_size_bytes(shrunk)
    if shrunk_raw_bytes <= max_raw_bytes:
        return PreparedLog(
            payload=shrunk,
            raw_bytes=shrunk_raw_bytes,
            request_bytes=payload_size_bytes(shrunk),
            truncated=True,
        )

    content_text = raw.get("content_text")
    if isinstance(content_text, str) and len(content_text) > max_raw_bytes // 2:
        keep = max(1024, (max_raw_bytes // 2) - 64)
        raw["content_text"] = f"{content_text[:keep]}…"
    shrunk_raw_bytes = raw_size_bytes(shrunk)
    if shrunk_raw_bytes <= max_raw_bytes:
        return PreparedLog(
            payload=shrunk,
            raw_bytes=shrunk_raw_bytes,
            request_bytes=payload_size_bytes(shrunk),
            truncated=True,
        )

    keep_fields = {
        "import",
        "sender",
        "record_type",
        "payload_type",
        "attachment_type",
        "session_id",
        "turn_id",
        "uuid",
        "parent_uuid",
        "prompt_id",
        "cwd",
        "project_name",
        "version",
        "git_branch",
        "entrypoint",
        "user_type",
        "permission_mode",
        "slug",
        "model",
        "originator",
        "cli_version",
        "source_app",
        "model_provider",
        "message_role",
        "request_id",
        "error",
        "stop_reason",
        "content_text",
        "tool_call_id",
        "tool_call_name",
    }
    shrunk["raw"] = {key: value for key, value in raw.items() if key in keep_fields}
    shrunk_raw_bytes = raw_size_bytes(shrunk)
    if shrunk_raw_bytes <= max_raw_bytes:
        return PreparedLog(
            payload=shrunk,
            raw_bytes=shrunk_raw_bytes,
            request_bytes=payload_size_bytes(shrunk),
            truncated=True,
        )

    content_text = shrunk["raw"].get("content_text")
    if isinstance(content_text, str):
        keep = max(512, max_raw_bytes - 4096)
        shrunk["raw"]["content_text"] = f"{content_text[:keep]}…"
    shrunk_raw_bytes = raw_size_bytes(shrunk)
    return PreparedLog(
        payload=shrunk,
        raw_bytes=shrunk_raw_bytes,
        request_bytes=payload_size_bytes(shrunk),
        truncated=True,
    )


def compact_for_upload(payload: dict[str, Any], *, max_raw_bytes: int) -> dict[str, Any]:
    return prepare_for_upload(payload, max_raw_bytes=max_raw_bytes).payload


def split_batch_by_size(batch: list[dict[str, Any]], *, max_batch_size: int, max_request_bytes: int) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_sizes: list[int] = []
    current_request_bytes = request_size_from_payload_sizes([])
    for payload in batch:
        payload_bytes = payload_size_bytes(payload)
        candidate_count = len(current) + 1
        candidate_bytes = current_request_bytes + payload_bytes + (1 if current else 0)
        if current and (candidate_count > max_batch_size or candidate_bytes > max_request_bytes):
            groups.append(current)
            current = [payload]
            current_sizes = [payload_bytes]
            current_request_bytes = request_size_from_payload_sizes(current_sizes)
            continue
        current.append(payload)
        current_sizes.append(payload_bytes)
        current_request_bytes = candidate_bytes
    if current:
        groups.append(current)
    return groups


RATE_LIMIT_MAX_RETRIES = 5


def _retry_after_seconds(response: httpx.Response) -> float:
    header = response.headers.get("Retry-After")
    if header:
        try:
            return max(1.0, float(header))
        except ValueError:
            pass
    return 5.0


def flush_batch(
    client: httpx.Client | None,
    batch: list[dict[str, Any]],
    *,
    dry_run: bool,
    rate_limit_attempt: int = 0,
) -> int:
    if not batch:
        return 0
    if dry_run:
        print(json.dumps({"logs": batch}, sort_keys=True))
        return len(batch)
    assert client is not None
    try:
        response = client.post("/ingest", json={"logs": batch})
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 413 and len(batch) > 1:
            midpoint = len(batch) // 2
            return flush_batch(client, batch[:midpoint], dry_run=dry_run) + flush_batch(client, batch[midpoint:], dry_run=dry_run)
        if exc.response.status_code == 429 and rate_limit_attempt < RATE_LIMIT_MAX_RETRIES:
            wait_s = _retry_after_seconds(exc.response)
            _log_progress(
                "rate_limited",
                attempt=rate_limit_attempt + 1,
                max_attempts=RATE_LIMIT_MAX_RETRIES,
                wait_s=wait_s,
                batch_size=len(batch),
            )
            time.sleep(wait_s)
            return flush_batch(client, batch, dry_run=dry_run, rate_limit_attempt=rate_limit_attempt + 1)
        raise
    return len(batch)


def run_scan(config: ScanConfig, parser: Parser | None = None) -> Counter[str]:
    scan_root = config.scan_path.expanduser().resolve()
    if not scan_root.exists():
        raise FileNotFoundError(f"scan path does not exist: {scan_root}")

    if parser is None:
        _log_progress("discovery_started", scan_root=str(scan_root), mode="auto")
        discovery_start = time.monotonic()
        project_files = discover_archive_files(scan_root)
        _log_progress(
            "discovery_complete",
            scan_root=str(scan_root),
            mode="auto",
            file_count=len(project_files),
            elapsed_s=round(time.monotonic() - discovery_start, 2),
        )
    else:
        scan_root, _ = parser.resolve_scan_root(config.scan_path)
        if not scan_root.exists():
            raise FileNotFoundError(f"scan path does not exist: {scan_root}")
        _log_progress("discovery_started", scan_root=str(scan_root), tool=parser.tool)
        discovery_start = time.monotonic()
        project_files = [(parser, path) for path in parser.iter_files(scan_root)]
        _log_progress(
            "discovery_complete",
            scan_root=str(scan_root),
            tool=parser.tool,
            file_count=len(project_files),
            elapsed_s=round(time.monotonic() - discovery_start, 2),
        )

    totals = Counter(files=0, lines=0, uploaded=0, skipped=0, truncated=0)
    if not project_files:
        return totals

    client: httpx.Client | None = None
    if not config.dry_run:
        timeout = httpx.Timeout(
            connect=10.0,
            read=config.request_timeout_s,
            write=config.request_timeout_s,
            pool=config.request_timeout_s,
        )
        client = httpx.Client(
            base_url=config.api_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {config.token}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def flush(batch_to_send: list[dict[str, Any]]) -> None:
        if not batch_to_send:
            return
        groups = split_batch_by_size(
            batch_to_send,
            max_batch_size=config.batch_size,
            max_request_bytes=config.request_target_bytes,
        )
        for group in groups:
            sent = flush_batch(client, group, dry_run=config.dry_run)
            totals["uploaded"] += sent
            _log_progress(
                "uploaded",
                count=sent,
                uploaded_total=totals["uploaded"],
                lines_total=totals["lines"],
                files_seen=totals["files"],
            )

    batch: list[dict[str, Any]] = []
    batch_request_bytes = request_size_from_payload_sizes([])

    def flush_current_batch() -> None:
        nonlocal batch, batch_request_bytes
        flush(batch)
        batch = []
        batch_request_bytes = request_size_from_payload_sizes([])

    try:
        for index, (file_parser, project_file) in enumerate(project_files, start=1):
            totals["files"] += 1
            file_start = time.monotonic()
            file_lines = 0
            file_context = build_file_context(file_parser, config, project_file)
            with project_file.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    payload = build_log_payload(
                        file_parser,
                        config,
                        record=record,
                        file_context=file_context,
                        line_number=line_number,
                    )
                    prepared = prepare_for_upload(payload, max_raw_bytes=config.raw_payload_max_bytes)
                    if prepared.raw_bytes > config.raw_payload_max_bytes:
                        totals["skipped"] += 1
                        _log_progress(
                            "skip_oversized_log",
                            file=str(project_file),
                            line_number=line_number,
                            session_id=payload["session_id"],
                        )
                        continue
                    if prepared.truncated:
                        totals["truncated"] += 1

                    candidate_count = len(batch) + 1
                    candidate_bytes = batch_request_bytes + prepared.request_bytes + (1 if batch else 0)
                    if batch and (candidate_count > config.batch_size or candidate_bytes > config.request_target_bytes):
                        flush_current_batch()
                        candidate_bytes = batch_request_bytes + prepared.request_bytes
                    batch.append(prepared.payload)
                    batch_request_bytes = candidate_bytes
                    totals["lines"] += 1
                    file_lines += 1
                    if len(batch) >= config.batch_size or batch_request_bytes >= config.request_target_bytes:
                        flush_current_batch()
            _log_progress(
                "file_complete",
                file=str(project_file),
                tool=file_parser.tool,
                progress=f"{index}/{len(project_files)}",
                lines=file_lines,
                elapsed_s=round(time.monotonic() - file_start, 2),
            )
        flush_current_batch()
    finally:
        if client is not None:
            client.close()
    return totals


def _build_config(
    *,
    api_url: str,
    token: str,
    source_name: str,
    hostname: str | None,
    scan_path: Path,
    batch_size: int,
    raw_payload_max_bytes: int,
    request_target_bytes: int,
    tag: list[str],
    dry_run: bool,
    request_timeout_s: float = DEFAULT_REQUEST_TIMEOUT_S,
) -> ScanConfig:
    if not api_url and not dry_run:
        raise typer.BadParameter("--api-url or LLMH_API_URL is required")
    if not token and not dry_run:
        raise typer.BadParameter("--token or LLMH_INGEST_TOKEN is required")

    return ScanConfig(
        api_url=api_url,
        token=token,
        source_name=source_name,
        hostname=hostname or source_name,
        scan_path=scan_path,
        batch_size=batch_size,
        raw_payload_max_bytes=raw_payload_max_bytes,
        request_target_bytes=request_target_bytes,
        dry_run=dry_run,
        tags=tag,
        request_timeout_s=request_timeout_s,
    )


@app.command("ship")
def ship(
    source_name: str = typer.Option(..., help="Logical source name to create/use in llmh."),
    scan_path: Path = typer.Option(
        Path("~/.codex/sessions").expanduser(),
        exists=False,
        file_okay=True,
        dir_okay=True,
        help="Path to scan for archive logs. Claude and Codex files are detected automatically.",
    ),
    api_url: str = typer.Option(default_factory=lambda: os.getenv("LLMH_API_URL", ""), help="API base URL."),
    token: str = typer.Option(default_factory=lambda: os.getenv("LLMH_INGEST_TOKEN", ""), help="Bearer ingest token."),
    hostname: str | None = typer.Option(default=None, help="Optional hostname override; defaults to source name."),
    batch_size: int = typer.Option(DEFAULT_BATCH_SIZE, min=1, max=1000, help="Number of log entries per upload batch."),
    raw_payload_max_bytes: int = typer.Option(
        DEFAULT_RAW_PAYLOAD_MAX_BYTES,
        min=1024,
        help="Maximum raw payload size to target per uploaded log.",
    ),
    request_target_bytes: int = typer.Option(
        DEFAULT_REQUEST_TARGET_BYTES,
        min=16384,
        help="Target maximum JSON request size per upload batch.",
    ),
    tag: list[str] = typer.Option(default_factory=list, help="Extra tag applied to every uploaded log."),
    request_timeout_s: float = typer.Option(
        DEFAULT_REQUEST_TIMEOUT_S,
        "--request-timeout",
        min=5.0,
        help="HTTP read/write timeout per upload request, in seconds.",
    ),
    dry_run: bool = typer.Option(default=False, help="Print payloads instead of uploading."),
) -> None:
    config = _build_config(
        api_url=api_url,
        token=token,
        source_name=source_name,
        hostname=hostname,
        scan_path=scan_path,
        batch_size=batch_size,
        raw_payload_max_bytes=raw_payload_max_bytes,
        request_target_bytes=request_target_bytes,
        tag=tag,
        dry_run=dry_run,
        request_timeout_s=request_timeout_s,
    )
    totals = run_scan(config)
    print(json.dumps(totals, sort_keys=True))


@app.command("ship-claude")
def ship_claude(
    source_name: str = typer.Option(..., help="Logical source name to create/use in llmh."),
    scan_path: Path = typer.Option(..., exists=False, file_okay=True, dir_okay=True, help="Path to scan for Claude archive logs."),
    api_url: str = typer.Option(default_factory=lambda: os.getenv("LLMH_API_URL", ""), help="API base URL."),
    token: str = typer.Option(default_factory=lambda: os.getenv("LLMH_INGEST_TOKEN", ""), help="Bearer ingest token."),
    hostname: str | None = typer.Option(default=None, help="Optional hostname override; defaults to source name."),
    batch_size: int = typer.Option(DEFAULT_BATCH_SIZE, min=1, max=1000, help="Number of log entries per upload batch."),
    raw_payload_max_bytes: int = typer.Option(
        DEFAULT_RAW_PAYLOAD_MAX_BYTES,
        min=1024,
        help="Maximum raw payload size to target per uploaded log.",
    ),
    request_target_bytes: int = typer.Option(
        DEFAULT_REQUEST_TARGET_BYTES,
        min=16384,
        help="Target maximum JSON request size per upload batch.",
    ),
    tag: list[str] = typer.Option(default_factory=list, help="Extra tag applied to every uploaded log."),
    request_timeout_s: float = typer.Option(
        DEFAULT_REQUEST_TIMEOUT_S,
        "--request-timeout",
        min=5.0,
        help="HTTP read/write timeout per upload request, in seconds.",
    ),
    dry_run: bool = typer.Option(default=False, help="Print payloads instead of uploading."),
) -> None:
    config = _build_config(
        api_url=api_url,
        token=token,
        source_name=source_name,
        hostname=hostname,
        scan_path=scan_path,
        batch_size=batch_size,
        raw_payload_max_bytes=raw_payload_max_bytes,
        request_target_bytes=request_target_bytes,
        tag=tag,
        dry_run=dry_run,
        request_timeout_s=request_timeout_s,
    )
    totals = run_scan(config, CLAUDE_PARSER)
    print(json.dumps(totals, sort_keys=True))


@app.command("ship-codex")
def ship_codex(
    source_name: str = typer.Option(..., help="Logical source name to create/use in llmh."),
    scan_path: Path = typer.Option(
        Path("~/.codex/sessions").expanduser(),
        exists=False,
        file_okay=True,
        dir_okay=True,
        help="Path to scan for Codex rollout logs (defaults to ~/.codex/sessions).",
    ),
    api_url: str = typer.Option(default_factory=lambda: os.getenv("LLMH_API_URL", ""), help="API base URL."),
    token: str = typer.Option(default_factory=lambda: os.getenv("LLMH_INGEST_TOKEN", ""), help="Bearer ingest token."),
    hostname: str | None = typer.Option(default=None, help="Optional hostname override; defaults to source name."),
    batch_size: int = typer.Option(DEFAULT_BATCH_SIZE, min=1, max=1000, help="Number of log entries per upload batch."),
    raw_payload_max_bytes: int = typer.Option(
        DEFAULT_RAW_PAYLOAD_MAX_BYTES,
        min=1024,
        help="Maximum raw payload size to target per uploaded log.",
    ),
    request_target_bytes: int = typer.Option(
        DEFAULT_REQUEST_TARGET_BYTES,
        min=16384,
        help="Target maximum JSON request size per upload batch.",
    ),
    tag: list[str] = typer.Option(default_factory=list, help="Extra tag applied to every uploaded log."),
    request_timeout_s: float = typer.Option(
        DEFAULT_REQUEST_TIMEOUT_S,
        "--request-timeout",
        min=5.0,
        help="HTTP read/write timeout per upload request, in seconds.",
    ),
    dry_run: bool = typer.Option(default=False, help="Print payloads instead of uploading."),
) -> None:
    config = _build_config(
        api_url=api_url,
        token=token,
        source_name=source_name,
        hostname=hostname,
        scan_path=scan_path,
        batch_size=batch_size,
        raw_payload_max_bytes=raw_payload_max_bytes,
        request_target_bytes=request_target_bytes,
        tag=tag,
        dry_run=dry_run,
        request_timeout_s=request_timeout_s,
    )
    totals = run_scan(config, CODEX_PARSER)
    print(json.dumps(totals, sort_keys=True))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
