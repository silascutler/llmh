# Architecture

## Locked Technical Decisions

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.12+, FastAPI (async) | SQLAlchemy 2.x async, Alembic, Pydantic v2 |
| Relational store | PostgreSQL 16 | Sources, logs, users, alert rules, alert events |
| Search | Meilisearch | Postgres is truth; logs mirrored on ingest |
| Ingestion | HTTP `POST /ingest` + Redis Streams | Worker reads from a configurable stream key |
| Source auth (ingest) | Shared bearer token (`INGEST_BEARER_TOKEN`) | Source identity carried in payload |
| User auth (UI) | Local username/password, cookie sessions | `passlib[argon2]` + Starlette `SessionMiddleware` |
| Alerts | Rule-based: keyword/regex/source/tag | Webhook (Slack/Discord JSON) + email (`aiosmtplib`) |
| Frontend | Next.js 15 (App Router) + TS + Tailwind + shadcn/ui | Lives in `web/`, talks to FastAPI as REST |
| Deploy | Docker Compose | Services: `api`, `worker`, `web`, `postgres`, `redis`, `meilisearch` |

## Repository Layout

```
llmh/
├── README.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docker/
│   ├── api.Dockerfile
│   ├── worker.Dockerfile
│   ├── web.Dockerfile
│   └── meilisearch.env
├── api/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── llmh/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app factory + uvicorn entry
│   │   ├── config.py          # pydantic-settings: env config
│   │   ├── db/
│   │   │   ├── base.py        # DeclarativeBase + naming convention
│   │   │   ├── session.py     # async engine + AsyncSession factory
│   │   │   └── models.py      # ORM models
│   │   ├── schemas/
│   │   │   ├── source.py
│   │   │   ├── log.py
│   │   │   ├── rule.py
│   │   │   ├── alert.py
│   │   │   ├── auth.py
│   │   │   └── common.py      # pagination, cursor types
│   │   ├── routers/
│   │   │   ├── auth.py        # /auth/*
│   │   │   ├── sources.py     # /sources
│   │   │   ├── ingest.py      # /ingest
│   │   │   ├── logs.py        # /logs (search)
│   │   │   ├── rules.py       # /rules
│   │   │   ├── alerts.py      # /alerts
│   │   │   └── health.py      # /healthz, /readyz
│   │   ├── services/
│   │   │   ├── sources.py
│   │   │   ├── logs.py        # ingest_one / ingest_batch
│   │   │   ├── rules.py
│   │   │   └── users.py
│   │   ├── search/
│   │   │   ├── client.py      # meilisearch async wrapper
│   │   │   └── index.py       # ensure_index, sync, search, backfill
│   │   ├── alerts/
│   │   │   ├── evaluator.py   # rule matching
│   │   │   ├── webhook.py     # httpx POST
│   │   │   └── email.py       # aiosmtplib
│   │   ├── auth/
│   │   │   ├── passwords.py   # passlib argon2
│   │   │   ├── sessions.py    # SessionMiddleware helpers
│   │   │   ├── deps.py        # current_user, require_admin
│   │   │   └── ingest_token.py
│   │   └── utils/
│   │       ├── ids.py
│   │       └── time.py
│   ├── scripts/
│   │   ├── create_admin.py    # bootstrap first admin user
│   │   └── reindex_meili.py   # backfill Meili from Postgres
│   └── tests/
│       ├── conftest.py
│       ├── test_sources.py
│       ├── test_ingest.py
│       ├── test_search.py
│       ├── test_rules.py
│       └── test_auth.py
├── worker/
│   ├── pyproject.toml         # depends on api/ as path dep, OR shared image
│   └── llmh_worker/
│       ├── __main__.py        # entrypoint: python -m llmh_worker
│       ├── redis_consumer.py  # Redis Streams consumer-group loop
│       └── alert_dispatcher.py
├── web/
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── components.json        # shadcn config
│   ├── .env.local.example
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── globals.css
│   │   ├── page.tsx           # dashboard
│   │   ├── login/page.tsx
│   │   ├── logout/route.ts
│   │   ├── sources/
│   │   │   ├── page.tsx
│   │   │   ├── new/page.tsx
│   │   │   └── [id]/page.tsx
│   │   ├── logs/page.tsx
│   │   ├── rules/
│   │   │   ├── page.tsx
│   │   │   ├── new/page.tsx
│   │   │   └── [id]/page.tsx
│   │   └── alerts/page.tsx
│   ├── components/
│   │   ├── ui/                # shadcn primitives
│   │   ├── nav.tsx
│   │   ├── log-table.tsx
│   │   ├── log-row.tsx
│   │   ├── source-form.tsx
│   │   ├── rule-form.tsx
│   │   └── search-bar.tsx
│   └── lib/
│       ├── api.ts             # fetch wrapper, sends cookies
│       ├── types.ts
│       └── auth.ts
└── client/
    ├── pyproject.toml
    ├── README.md
    └── llmh_client/
        └── __main__.py        # `llmh-client ship --source-name laptop --scan-path ~/.codex`
```

## Backend Module Responsibilities (`api/`)

- **`llmh/main.py`** — `create_app()` returns FastAPI app. Mounts routers, `SessionMiddleware`, CORS for the web origin, exception handlers, and a startup hook that calls `search.index.ensure_index()`.
- **`llmh/config.py`** — `Settings(BaseSettings)` reads all env (see [deployment.md](deployment.md)).
- **`llmh/db/session.py`** — `async_engine = create_async_engine(settings.database_url, pool_size=10)`, `AsyncSessionLocal`, `get_session()` FastAPI dependency.
- **`llmh/db/models.py`** — ORM models (see [data-model.md](data-model.md)).
- **`llmh/services/logs.py`** — `async def ingest(session, payloads) -> list[Log]`. Resolves source, persists rows in a transaction, mirrors to Meilisearch, then calls `alerts.evaluator.evaluate_for(logs)`.
- **`llmh/search/index.py`** — `INDEX = "logs"`. `ensure_index()`, `index_logs(rows)`, `search(params)`, `delete_log(id)`, `backfill()`.
- **`llmh/alerts/evaluator.py`** — pure `match(rule, log) -> bool`, plus `evaluate_for(logs, session)` with a 30-second TTL in-process rule cache.
- **`llmh/auth/deps.py`** — `current_user`, `require_admin`, `require_ingest_token` FastAPI dependencies.

## Library Pins (rough)

```
fastapi>=0.115
uvicorn[standard]>=0.30
sqlalchemy[asyncio]>=2.0
asyncpg>=0.29
alembic>=1.13
pydantic>=2.7
pydantic-settings>=2.3
passlib[argon2]>=1.7
itsdangerous>=2.2
meilisearch-python-sdk>=4   # async client; do not write a custom HTTP client
redis>=5
httpx>=0.27
aiosmtplib>=3.0
email-validator
python-multipart

# dev
pytest
pytest-asyncio
ruff
mypy
```

## Critical Files

- `docker-compose.yml`
- `api/llmh/main.py`
- `api/llmh/db/models.py`
- `api/llmh/services/logs.py`
- `api/llmh/search/index.py`
- `api/llmh/routers/ingest.py`
- `api/llmh/alerts/evaluator.py`
- `worker/llmh_worker/redis_consumer.py`
- `web/app/logs/page.tsx`
- `client/llmh_client/__main__.py`
