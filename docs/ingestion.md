# Ingestion

Two transports, both routed through the same service function `services.logs.ingest()` so behavior stays consistent. Postgres commits first; Meilisearch is mirrored after; alerts evaluate inline. See [search.md](search.md) for the Meili side and [alerts.md](alerts.md) for the rule evaluation.

## 1. HTTP `POST /ingest`

- **Auth**: `Authorization: Bearer ${INGEST_BEARER_TOKEN}` (constant-time compare in `auth/ingest_token.py`).
- **Body**: always `{"logs": [...]}`. Max 500 entries per batch (configurable via `INGEST_BATCH_MAX`).
- **Status**: 202 Accepted, returns `{"ids": ["uuid", ...]}`.

### Per-log payload

```json
{
  "source_id": "uuid",
  "source_key": {
    "hostname": "host.example",
    "ip_address": "10.0.0.5",
    "port": 22,
    "name": "claude-laptop",
    "tags": ["dev"]
  },
  "tool": "claude-code",
  "session_id": "abc123",
  "level": "info",
  "message": "string",
  "raw": { "...": "..." },
  "tags": ["build"],
  "occurred_at": "2026-04-27T18:11:00Z"
}
```

- Exactly one of `source_id` / `source_key` is required.
- If `source_key` is given and no source matches the unique tuple `(hostname, ip_address, port)`, **auto-create** the source.
- Unknown `source_id` → 404.
- `level` validated against enum.
- `occurred_at` must be parseable ISO-8601.
- `raw` size capped at `RAW_PAYLOAD_MAX_BYTES` (default 64 KiB).

### Endpoint signature

```python
@router.post("/ingest", status_code=202,
             dependencies=[Depends(require_ingest_token)])
async def ingest(
    body: LogIngestBatch,
    session: AsyncSession = Depends(get_session),
) -> IngestResponse:
    ...
```

## 2. Redis Streams worker

Lives in `worker/llmh_worker/redis_consumer.py`. Imports `services.logs.ingest()` from the API package so semantics match.

- **Stream key**: `REDIS_INGEST_STREAM` (default `llmh:ingest`).
- **Consumer group**: `REDIS_CONSUMER_GROUP` (default `llmh-workers`).
- **Consumer name**: `${HOSTNAME}-${pid}`.
- **Message format**: `XADD llmh:ingest * payload <json>` where `<json>` is exactly one log entry (same shape as the HTTP per-log payload). One log per stream message keeps replay/recovery simple.
- **Acks**: `XACK` only after Postgres commit + Meili index attempt. Failures stay in PEL.
- **Reaper**: periodic `XAUTOCLAIM` for messages > 60s old in the PEL.
- **Delivery semantics**: at-least-once. Duplicates tolerated in v1; optional `idempotency_key` field can be added later for dedupe.

### Consumer loop sketch

```python
ensure_group(stream, group)  # MKSTREAM, idempotent
while True:
    msgs = await redis.xreadgroup(
        group, consumer, streams={stream: ">"}, count=64, block=5000
    )
    for msg_id, fields in flatten(msgs):
        try:
            payload = json.loads(fields[b"payload"])
            await services.logs.ingest(session, [payload])
            await redis.xack(stream, group, msg_id)
        except Exception:
            log.exception("ingest failed for %s", msg_id)
            # leave unacked → PEL; reclaim later via XAUTOCLAIM
```

## Service function — single source of truth

`api/llmh/services/logs.py`:

```python
async def ingest(
    session: AsyncSession,
    payloads: list[LogIngest],
) -> list[Log]:
    # 1. resolve/create source (per-payload)
    # 2. insert logs in one bulk INSERT ... RETURNING
    # 3. await session.commit()
    # 4. await search.index.index_logs(rows)        # mirror to Meili
    # 5. await alerts.evaluator.evaluate_for(rows)  # inline alert dispatch
    return rows
```

If Meilisearch indexing fails, the rows are still in Postgres. Push the failed IDs onto a Redis list `llmh:meili:retry` for the worker to retry later. Postgres is the source of truth.
