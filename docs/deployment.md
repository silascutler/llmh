# Deployment

The full stack runs under Docker Compose. For day-to-day operations, use the repo `Makefile` instead of typing raw Compose and script commands.

## Services

| Service | Image / Build | Notes |
|---|---|---|
| `postgres` | `postgres:16` | Persistent volume |
| `redis` | `redis:7` | Streams + retry list |
| `meilisearch` | `getmeili/meilisearch:v1.10` | Persistent volume; uses `MEILI_MASTER_KEY` |
| `api` | `docker/api.Dockerfile` | Runs `alembic upgrade head && uvicorn llmh.main:app --host 0.0.0.0 --port 8000` |
| `worker` | `docker/worker.Dockerfile` | Runs `python -m llmh_worker` |
| `web` | `docker/web.Dockerfile` | Next.js standalone build, `next start` on port 3000 |

`api` and `worker` share the same Python codebase (`api/llmh`); the worker imports `services.logs.ingest` directly.

`api` and `worker` `depends_on: [postgres, redis, meilisearch]`. `web` `depends_on: [api]`.

## Environment Variables (`.env.example`)

```
# --- Postgres ---
POSTGRES_DB=llmh
POSTGRES_USER=llmh
POSTGRES_PASSWORD=changeme
DATABASE_URL=postgresql+asyncpg://llmh:changeme@postgres:5432/llmh

# --- Redis ---
REDIS_URL=redis://redis:6379/0
REDIS_INGEST_STREAM=llmh:ingest
REDIS_CONSUMER_GROUP=llmh-workers

# --- Meilisearch ---
MEILI_URL=http://meilisearch:7700
MEILI_MASTER_KEY=changeme-please-32-chars-min-aaaaa

# --- API ---
INGEST_BEARER_TOKEN=replace-with-long-random-string
SESSION_SECRET=replace-with-long-random-string
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
RAW_PAYLOAD_MAX_BYTES=65536
INGEST_BATCH_MAX=500

# --- SMTP (optional) ---
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=llmh@localhost
SMTP_STARTTLS=true

# --- Web ---
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## End-to-End Verification

```bash
# 1. Bring up the stack
cd /home/silas/Development/llmh
cp .env.example .env
# (edit secrets — INGEST_BEARER_TOKEN, SESSION_SECRET, MEILI_MASTER_KEY)
make restart
docker compose logs -f api    # watch alembic + uvicorn ready

# 2. Seed admin
make user-add USERNAME=silas PASSWORD='changeme!' ROLE=admin

# 3. Log into UI: http://localhost:3001/login

# 4. Create a source via API (using login cookie)
curl -s -c cookies.txt -b cookies.txt -X POST http://localhost:8000/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"silas","password":"changeme!"}'

SOURCE_ID=$(curl -s -b cookies.txt -X POST http://localhost:8000/sources \
  -H 'content-type: application/json' \
  -d '{"name":"laptop","hostname":"silas-laptop","ip_address":"10.0.0.5","tags":["dev"]}' | jq -r .id)

# 5. Send a log via HTTP ingest
curl -s -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer $INGEST_BEARER_TOKEN" \
  -H 'content-type: application/json' \
  -d "{\"logs\":[{\"source_id\":\"$SOURCE_ID\",\"tool\":\"claude-code\",
        \"level\":\"error\",\"message\":\"build failed: missing token\",
        \"raw\":{\"argv\":[\"claude\",\"build\"]},
        \"tags\":[\"build\"],\"occurred_at\":\"2026-04-27T18:11:00Z\"}]}"

# 6. Search via UI: visit /logs, search "missing token"

# 7. Send via Redis Streams (alternate path)
docker compose exec redis redis-cli XADD llmh:ingest '*' payload \
  "{\"source_id\":\"$SOURCE_ID\",\"tool\":\"claude-code\",\"level\":\"warn\",
    \"message\":\"redis path\",\"raw\":{},\"tags\":[],
    \"occurred_at\":\"2026-04-27T18:12:00Z\"}"

# 8. Configure rule via /rules/new (keyword="missing token", webhook URL).
#    Send another matching log; observe webhook hit + row in /alerts.

# 9. Standalone client smoke test (uploads an archive on disk)
cd client && pip install -e .
LLMH_API_URL=http://localhost:8000 LLMH_INGEST_TOKEN=$INGEST_BEARER_TOKEN \
  llmh-client ship --source-name $(hostname) --scan-path ~/.codex/sessions
# Verify in UI: codex rollouts visible under the source matching $(hostname)
```

## Operator Commands

Use the top-level `Makefile` for common production operations:

```bash
make start
make stop
make status
make logs
make user-list
make user-add USERNAME=viewer1 PASSWORD='replace-me' ROLE=viewer
make user-delete USERNAME=viewer1
make user-set-password USERNAME=silas PASSWORD='new-secret'
make user-reset-link USERNAME=silas BASE_URL=https://llmh.example.com PRINT_URL=true
```

`make user-reset-link` prints the reset token by default. Set `PRINT_URL=true` if you explicitly want the full `/reset-password?token=...` URL. This works without email infrastructure and is intended for operator-issued resets.

## Production Deployment

Use `docker-compose.prod.yml` with a Cloudflare Tunnel token when you want to expose the app through Cloudflare instead of binding public ports on the host.

```bash
cp .env.example .env
# Fill in production secrets and set CLOUDFLARED_TUNNEL_TOKEN
make prod-build
make prod-start
```

The production compose file starts `cloudflared` alongside the app stack and removes host port publishing from the internal services. Configure the tunnel in Cloudflare to route the public web hostname to the `web` service, and the public API hostname to the `api` service if you plan to expose the API directly through the tunnel.

## Operational Notes

- Postgres data volume must persist across deploys (loses logs otherwise).
- Meili volume is rebuildable from Postgres via `scripts/reindex_meili.py`, so loss is recoverable.
- `INGEST_BEARER_TOKEN` and `SESSION_SECRET` should be at least 32 chars of random.
- For Cloudflare Tunnel or any TLS-terminating edge, set `SESSION_HTTPS_ONLY=true` in `.env` so session cookies are marked secure.
- The app now prefers `CF-Connecting-IP`, then `X-Forwarded-For`, then the direct socket address when it derives the requestor IP for throttling.
- The default `docker-compose.yml` only publishes services on `127.0.0.1`; do not expose Postgres, Redis, or Meilisearch directly to the public internet.
- Set `NEXT_PUBLIC_API_BASE_URL` to the public API origin exposed through the tunnel, and include the public web origin in `CORS_ORIGINS`.
- The login screen now includes a reset-password entry point. Operators generate reset links with `make user-reset-link`.
