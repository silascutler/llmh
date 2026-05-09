# API Endpoints

This doc covers `/sources`, `/auth`, and `/alerts`. See [ingestion.md](ingestion.md) for `/ingest` and [search.md](search.md) for `/logs`.

All endpoints are JSON. UI uses cookie sessions (`credentials: "include"`); ingestion uses `Authorization: Bearer ...`.

## Authentication

### `POST /auth/login`
Body: `{"username": "...", "password": "..."}`.
Verifies via `passlib.argon2`. On success: `request.session["uid"] = str(user.id)` and returns `UserOut`.

### `POST /auth/logout`
`request.session.clear()`.

### `GET /auth/me`
Returns current `UserOut` or `401`.

### Session config
- Starlette `SessionMiddleware`
- `secret_key = settings.session_secret`
- `same_site = "lax"`
- Cookie name `llmh_session`
- Max age 14 days
- `https_only` configurable

### Bootstrap
`api/scripts/create_admin.py` — argparse `--username`/`--password`, hashes with argon2, inserts a user with `role='admin'`. Run via:
```
docker compose run --rm api python -m scripts.create_admin --username silas --password 'changeme!'
```

## Sources — `/sources`

Auth: viewer reads, admin writes.

| Method | Path | Notes |
|---|---|---|
| GET    | `/sources`             | List with optional `q`, `tag`, pagination |
| POST   | `/sources`             | Create. 409 on unique violation |
| GET    | `/sources/{id}`        | Detail + last-seen log timestamp (`MAX(occurred_at)`) |
| PATCH  | `/sources/{id}`        | Partial update |
| DELETE | `/sources/{id}`        | Cascades logs + alert_events |
| GET    | `/sources/{id}/stats`  | Counts by level across all logs |

Body for POST/PATCH:
```json
{
  "name": "claude-laptop",
  "hostname": "silas-laptop",
  "ip_address": "10.0.0.5",
  "port": 22,
  "notes": "office macbook",
  "tags": ["dev", "personal"]
}
```

## Alert Rules — `/rules`

Standard CRUD. Admin-only writes. See [alerts.md](alerts.md) for evaluation semantics.

| Method | Path | Notes |
|---|---|---|
| GET    | `/rules`        | List |
| POST   | `/rules`        | Create |
| GET    | `/rules/{id}`   | Detail |
| PATCH  | `/rules/{id}`   | Partial update (e.g. toggle `enabled`) |
| DELETE | `/rules/{id}`   | Delete; cascades alert_events |

Body:
```json
{
  "name": "auth failures",
  "enabled": true,
  "match_type": "keyword",          // keyword | regex | source | tag
  "match_value": "missing token",
  "source_filter": null,            // optional uuid
  "tag_filter": null,               // optional string[]
  "webhook_url": "https://hooks.slack.com/services/...",
  "email_to": "ops@example.com"
}
```

Validation: when `match_type == "regex"`, the Pydantic validator compiles `match_value` and rejects invalid patterns at input time.

## Alerts — `/alerts`

| Method | Path | Notes |
|---|---|---|
| GET    | `/alerts`         | Recent events; filters: `rule_id`, `from`, `to`, pagination |

Each item joins the rule (`rule_name`) and a log preview (`log_message`, `source_name`, `occurred_at`) plus `delivery_status`.

## Health

| Method | Path | Notes |
|---|---|---|
| GET    | `/healthz` | Liveness — process up |
| GET    | `/readyz`  | Readiness — DB + Meili reachable |
