# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Self-hosted web app for archiving, searching, and alerting on logs emitted by CLI LLM tools (Claude Code, Codex, Aider, etc.). The stack is locked; see `docs/architecture.md` and `docs/phases.md` before changing structural decisions.

## Docker-first workflow

Everything runs in Docker Compose. The host rarely runs Python directly — even tests run inside the `api` container. Confirm `docker context show` returns `rootless` before invoking compose; never run ad-hoc DB-mutating scripts outside pytest.

```bash
cp .env.example .env       # one-time
make build                 # docker compose build
make start                 # up -d
make logs                  # tail
make stop
```

Production overlay: `make prod-build` / `make prod-start` (uses `docker-compose.prod.yml` with the `cloudflared` service).

## User management (admin bootstrap)

```bash
make user-add USERNAME=alice PASSWORD=secret ROLE=admin
make user-list
make user-set-password USERNAME=alice PASSWORD=newsecret
make user-reset-link USERNAME=alice BASE_URL=http://localhost:3001
```

These wrap `python -m scripts.<name>` inside the api container.

## Tests

```bash
docker compose run --rm api pytest                          # all api tests
docker compose run --rm api pytest tests/test_ingest.py     # one file
docker compose run --rm api pytest tests/test_ingest.py::test_name -x
docker compose run --rm web npm test                        # vitest (run mode)
```

The api conftest creates a separate `llmh_api_test` Postgres database and uses `Base.metadata.create_all` rather than alembic — schema drift between models and migrations will not be caught by tests. When adding a migration, also verify the model definitions match.

Each test wipes Postgres tables, the Meili index, the Redis rate-limit keys, and the in-process metrics. Tests need live `postgres`, `redis`, and `meilisearch` services running.

## Database migrations

Alembic versions live in `api/alembic/versions/`. The api container's start command runs `python -m scripts.ensure_schema && alembic upgrade head` before uvicorn, so a fresh `make start` migrates automatically.

```bash
docker compose run --rm api alembic revision -m "description" --autogenerate
docker compose run --rm api alembic upgrade head
docker compose run --rm api alembic downgrade -1
```

Initial migration enables the `pgcrypto` and `citext` extensions; preserve those.

## Architecture — the parts that span files

**Single ingest funnel.** Both `POST /ingest` (HTTP, in `api/llmh/routers/ingest.py`) and the Redis Streams worker (`worker/llmh_worker/redis_consumer.py`) call the same `api/llmh/services/logs.py::ingest()`. Don't add ingest logic in either entry point — put it in the service so both transports inherit it.

**Postgres is the source of truth; Meili is mirrored asynchronously.** `services.logs.ingest()` commits to Postgres, then pushes new log IDs onto the Redis list `llmh:meili:retry` (constant `MEILI_RETRY_LIST`). The worker drains that list into Meilisearch. If Meili is unavailable, Postgres rows are still authoritative — the retry list will eventually catch up. Search reads (`GET /logs`) hit Meili and rehydrate full rows from Postgres by ID.

**Source resolution by name + auto-create.** Each ingest payload carries either `source_id` or `source_key`. `source_key.name` is the canonical lookup; `_resolve_source` will reuse an existing source by name (filling in null hostname/ip/port from the new payload) or create one. Sources have a UNIQUE constraint on `name`.

**Idempotency.** Logs may carry `idempotency_key`; `services.logs.ingest()` short-circuits both within-batch duplicates and previously-stored ones. The dedupe applies to both HTTP and Redis ingest paths.

**Alert evaluation is inline.** After commit + Meili-retry-push, `alerts.evaluator.evaluate_for(rows, session)` runs synchronously, matches against a 30s in-process rule cache, dispatches webhooks (`alerts/webhook.py`) and email (`alerts/email.py`), and writes `alert_events` rows with `delivery_status` JSON. The `rule_notifications.py` Postgres `LISTEN/NOTIFY` listener (started in `main.py` lifespan) invalidates the cache when rules change.

**Auth has two completely separate paths.**
- Ingest: shared bearer token `INGEST_BEARER_TOKEN`, constant-time compared in `auth/ingest_token.py`.
- UI/API: argon2 password hashes (`auth/passwords.py`) + Starlette `SessionMiddleware` cookie sessions (`auth/sessions.py`). Dependencies `current_user` and `require_admin` live in `auth/deps.py`.

**Frontend.** Next.js 15 App Router under `web/`. Authenticated pages are in `web/app/(protected)/`. `lib/api.ts` is the client-side fetch wrapper (sends cookies); `lib/server-api.ts` is for server components. Tests are vitest with `@testing-library/react` and jsdom. Build args `NEXT_PUBLIC_API_BASE_URL` (browser) and `API_INTERNAL_BASE_URL` (server-side, defaults to `http://api:8000` inside the compose network) must both be set.

**Standalone client (`client/`)** is a Typer CLI run on the host (not Docker). `llmh-client ship` autodetects Claude `projects/**/*.jsonl` and Codex `rollout-*.jsonl` archives, registers/reuses a source by `--source-name`, batches uploads to `/ingest`, and trims oversized `raw.record` payloads to fit `RAW_PAYLOAD_MAX_BYTES`.

## Configuration

All settings flow through `api/llmh/config.py::Settings` (pydantic-settings, reads `.env`). Key knobs:

- `RAW_PAYLOAD_MAX_BYTES` — 64 KiB default; ingest returns 413 above this.
- `INGEST_BATCH_MAX` — 500 entries per batch.
- `INGEST_RATE_LIMIT_PER_MINUTE` — Redis-backed limiter.
- `SESSION_HTTPS_ONLY` — set false only for plain-HTTP local dev.
- `CORS_ORIGINS` accepts a JSON list or comma-separated string.

## Implementation status

Phases A–F (scaffold → search → worker → alerts → frontend → archive client) are largely complete. Phase G polish (`docs/phases.md`) covers `LISTEN/NOTIFY` rule cache invalidation, alert delivery retries, idempotency keys, Prometheus `/metrics` — most are landed; consult git log for current state.

## Critical files

- `api/llmh/services/logs.py` — the ingest funnel
- `api/llmh/routers/ingest.py` — HTTP entry
- `worker/llmh_worker/redis_consumer.py` — Redis Streams entry + Meili retry drain
- `api/llmh/search/index.py` — Meili index lifecycle
- `api/llmh/alerts/evaluator.py` — rule cache + matching
- `api/llmh/db/models.py` — ORM (must match Alembic migrations)
- `api/tests/conftest.py` — test DB + cleanup fixtures
- `client/llmh_client/__main__.py` — CLI entry
