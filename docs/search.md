# Search

Meilisearch is the full-text search engine. Postgres remains the source of truth; Meili is a derived index, fully rebuildable from Postgres at any time via `scripts/reindex_meili.py`.

## Index Configuration

- **Index name**: `logs`
- **Primary key**: `id`

### Document shape (flat mirror of Log row)

```json
{
  "id": "uuid",
  "source_id": "uuid",
  "source_name": "claude-laptop",
  "tool": "claude-code",
  "session_id": "abc123",
  "level": "error",
  "message": "build failed: missing token",
  "tags": ["build"],
  "occurred_at_ts": 1745781060,
  "received_at_ts": 1745781061
}
```

`source_name` is denormalized so the UI can show source labels and filter chips without an extra join.
Timestamps are stored as unix-int so Meili can sort them.

### Settings (idempotent on startup)

```json
{
  "searchableAttributes": ["message", "tool", "source_name", "tags", "session_id"],
  "filterableAttributes": ["source_id", "tool", "level", "tags", "occurred_at_ts"],
  "sortableAttributes":   ["occurred_at_ts", "received_at_ts"],
  "rankingRules": [
    "words", "typo", "proximity", "attribute", "sort", "exactness",
    "occurred_at_ts:desc"
  ],
  "pagination": { "maxTotalHits": 10000 }
}
```

`api/llmh/search/index.py:ensure_index()` is called from the FastAPI startup hook and is idempotent.

## Sync Strategy

**Write-through on ingest.** In `services.logs.ingest()`:

1. Bulk INSERT logs.
2. `await session.commit()` — Postgres committed first.
3. `await search.index.index_logs(rows)` — mirror to Meili.
4. On Meili failure: push log IDs onto Redis list `llmh:meili:retry`. The worker drains this list separately.

## Backfill

`api/scripts/reindex_meili.py`:
- Streams `logs` rows ordered by `received_at` in batches of 1000.
- Pushes each batch to `index_logs()`.
- Idempotent because the primary key is `id`.

Run via:
```
docker compose run --rm api python -m scripts.reindex_meili
```

## Search API — `GET /logs`

Auth: requires logged-in user.

### Query parameters

| Param | Type | Notes |
|---|---|---|
| `q` | string | Full-text query against Meili |
| `source_id` | uuid | Filter |
| `tool` | string | Filter |
| `level` | enum | `debug`/`info`/`warn`/`error` |
| `tags` | repeatable string | Any-of |
| `from` | ISO-8601 | `occurred_at >=` |
| `to` | ISO-8601 | `occurred_at <=` |
| `session_id` | string | Filter |
| `limit` | int (default 50, max 200) | Page size |
| `cursor` | opaque string | Base64-encoded `{offset}` from Meili |

### Behavior

1. **With `q` or any filter** → query Meili:
   - Build filter expression (e.g. `level = 'error' AND source_id = '...' AND occurred_at_ts >= 1745... AND tags IN ['build']`).
   - `sort: ["occurred_at_ts:desc"]`.
   - Apply `offset` and `limit`.
   - Take returned `hits[].id` and hydrate full log rows from Postgres in one `SELECT ... WHERE id = ANY($1)` joining sources for `source_name`. Preserve Meili order client-side via a map.

2. **Empty `q` and no filters** → bypass Meili. Serve straight from Postgres ordered `occurred_at DESC`. This is the cheap "recent logs" path for the dashboard.

### Response

```json
{
  "items": [ /* LogOut, ... */ ],
  "next_cursor": "base64-or-null",
  "estimated_total": 12345
}
```
