# Implementation Phases

The coding agent should implement in this order. Each phase ends in a runnable, testable state — do not advance until the test for the previous phase passes.

## Phase A — Scaffolding + DB + Sources CRUD

1. Repo skeleton matching [architecture.md](architecture.md): `api/`, `worker/`, `web/`, `tools/`, `docker/`.
2. `pyproject.toml` files for `api/`, `worker/`, `client/`. `.env.example`, `.gitignore`.
3. `docker-compose.yml` with `postgres`, `redis`, `meilisearch` (api/worker/web added in later phases).
4. FastAPI app boot (`main.py`, `config.py`), async engine, Alembic with the initial migration creating **all** tables (sources, users, logs, alert_rules, alert_events) and `pgcrypto` + `citext`.
5. Auth module (`passlib[argon2]`, `SessionMiddleware`, deps), `scripts/create_admin.py`, `/auth/login|logout|me`.
6. `/sources` CRUD + tests.

**Done when:** `pytest` passes; you can log in via curl and create/list a source.

## Phase B — HTTP Ingest + Meilisearch + Search

1. `search/index.py` with `ensure_index()` called from FastAPI startup.
2. `services/logs.ingest()`, `POST /ingest` endpoint with bearer auth (see [ingestion.md](ingestion.md)).
3. `scripts/reindex_meili.py` for backfill.
4. `GET /logs` with hybrid Meili+Postgres flow (see [search.md](search.md)).

**Done when:** curl ingest → curl `/logs?q=...` returns the hit; reindex script also populates Meili from a clean state.

## Phase C — Redis Streams Worker

1. `worker/` package, Dockerfile, compose service.
2. Consumer-group loop calling shared `services.logs.ingest()` (see [ingestion.md](ingestion.md)).
3. Periodic `XAUTOCLAIM` reaper for stuck PEL entries.
4. Drain handler for the `llmh:meili:retry` list.

**Done when:** `XADD llmh:ingest * payload <json>` from `redis-cli` results in a log row appearing in Postgres, indexed in Meili, and visible via the search API.

## Phase D — Alerts

1. `/rules` CRUD with regex compile validation.
2. `alerts/evaluator.py` invoked from `services.logs.ingest()` after Meili sync (see [alerts.md](alerts.md)).
3. Webhook (`alerts/webhook.py`) and email (`alerts/email.py`) delivery.
4. `alert_events` rows with `delivery_status` updates.
5. `GET /alerts` listing with rule + log preview.

**Done when:** A keyword rule with a `webhook.site` URL fires when a matching log is ingested. Webhook is hit; an `alert_events` row appears with `delivery_status.webhook.status_code = 200`.

## Phase E — Frontend

1. Scaffold Next.js 15: `npx create-next-app@latest web --typescript --tailwind --app --eslint`.
2. `npx shadcn init` and add the primitives listed in [frontend.md](frontend.md).
3. `lib/api.ts`, `lib/types.ts`, login page, auth gate.
4. Pages: dashboard, sources (list/new/detail), logs search, rules (list/new/detail), alerts feed.
5. Add `web` service to `docker-compose.yml`.

**Done when:** Full UI walkthrough per [deployment.md §End-to-End Verification](deployment.md) succeeds with no curl needed beyond initial login.

## Phase F — Standalone Archive Client

1. `client/llmh_client/` Typer CLI that uploads Claude project JSONL archives and Codex rollout sessions to `/ingest`.
2. Auto-detect parser per file; one source row per `--source-name` (server resolves by name).
3. Batch + size-aware splitting with progress events on stderr.
4. README with usage examples for `ship`, `ship-claude`, `ship-codex`.

**Done when:** `llmh-client ship --source-name laptop --scan-path ~/.codex/sessions` discovers Codex rollouts, registers/reuses the source, and produces a coherent transcript view in the UI.

## Phase G — Optional Polish

Defer until A–F are stable:

- `LISTEN/NOTIFY` on `alert_rules_changed` for instant rule cache invalidation.
- Alert delivery retries with exponential backoff (background queue).
- Per-source ingest tokens to replace the shared bearer token.
- Prometheus `/metrics` endpoint.
- `idempotency_key` on log payloads for dedupe across HTTP + Redis.
