# Standalone Client

Host-runnable client for scanning a directory tree, finding agent archive logs (Claude Code or Codex), and uploading them to `llmh`.

## Package

- Path: `client/`
- Console script: `llmh-client`
- Runtime: host Python, not Docker

## Commands

### `ship` — autodetects Claude and Codex archives

```bash
cd client
pip install -e .

LLMH_API_URL=http://localhost:8000 \
LLMH_INGEST_TOKEN=your-token \
llmh-client ship \
  --source-name prod-archive-185.237.218.186 \
  --scan-path /home/silas/Mount/dumpsterfire/202604/185.237.218.186_8080/185.237.218.186:8080/
```

The client will:

1. Resolve the enclosing `<IP>_<PORT>` source directory when the scan path is nested under one.
2. Discover Claude `projects/**/*.jsonl` files and Codex `rollout-*.jsonl` files automatically.
3. Parse each record using the matching archive rules for that file type.
4. Auto-register or reuse a source through `source_key`.
5. Upload logs to `/ingest` in batches.

Uploaded logs keep the archive-specific tags (`claude-archive` or `codex-archive`) along with any extra `--tag` values.

The legacy `ship-claude` and `ship-codex` commands still exist as explicit overrides, but the default `ship` command should cover normal usage.

```bash
LLMH_API_URL=http://localhost:8000 \
LLMH_INGEST_TOKEN=your-token \
llmh-client ship-claude \
  --source-name claude-laptop \
  --scan-path /path/to/claude/archive
```

## Common options

- `--source-name` (required) — logical source name to create or reuse.
- `--scan-path` — directory or file to scan. The generic `ship` command defaults to `~/.codex/sessions`.
- `--hostname` — overrides `--source-name` for the source's `hostname` field.
- `--dry-run` — prints exact ingest payloads without uploading.
- `--tag` — extra tag applied to every uploaded log (repeatable).
- `--batch-size` — entries per upload batch (default 100).
- `--raw-payload-max-bytes` — per-log raw payload cap (default 65536, matches the server limit).
- `--request-target-bytes` — target maximum request size (default 524288).

If a single record is too large, the client preserves core transcript/session context and trims bulky `raw.record` / tool payload fields before upload, then splits batches automatically if the API rejects them as too large.
