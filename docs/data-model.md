# Data Model

PostgreSQL 16. UUID PKs default `gen_random_uuid()`. Sources and logs are always linked by FK — there is no orphaned log path.

The initial Alembic migration enables the `pgcrypto` and `citext` extensions.

## Tables

### sources
```
id              uuid PK default gen_random_uuid()
name            text NOT NULL
hostname        text NOT NULL
ip_address      inet
port            integer
notes           text
tags            text[] NOT NULL DEFAULT '{}'
created_at      timestamptz NOT NULL DEFAULT now()
updated_at      timestamptz NOT NULL DEFAULT now()

UNIQUE (hostname, ip_address, port)
INDEX (name)
GIN INDEX on tags
```

### users
```
id              uuid PK default gen_random_uuid()
username        citext UNIQUE NOT NULL
password_hash   text NOT NULL
role            text NOT NULL CHECK (role IN ('admin','viewer'))
created_at      timestamptz NOT NULL DEFAULT now()
```

### logs
```
id              uuid PK default gen_random_uuid()
source_id       uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE
tool            text NOT NULL                 -- e.g. "claude-code", "codex", "aider"
session_id      text
level           text NOT NULL CHECK (level IN ('debug','info','warn','error'))
message         text NOT NULL
raw             jsonb NOT NULL                -- original full payload
tags            text[] NOT NULL DEFAULT '{}'
occurred_at     timestamptz NOT NULL          -- from source
received_at     timestamptz NOT NULL DEFAULT now()  -- server-side

INDEX (source_id, occurred_at DESC)
INDEX (tool)
INDEX (occurred_at DESC)
GIN INDEX on tags
-- optional: GIN on raw (jsonb_path_ops) for structured queries
```

`source_id` is `NOT NULL` — every log must be linked to a source.

### alert_rules
```
id              uuid PK default gen_random_uuid()
name            text NOT NULL
enabled         boolean NOT NULL DEFAULT true
match_type      text NOT NULL CHECK (match_type IN ('keyword','regex','source','tag'))
match_value     text NOT NULL
source_filter   uuid REFERENCES sources(id) ON DELETE SET NULL
tag_filter      text[]
webhook_url     text
email_to        text
created_by      uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT
created_at      timestamptz NOT NULL DEFAULT now()

INDEX (enabled)
```

### alert_events
```
id              uuid PK default gen_random_uuid()
rule_id         uuid NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE
log_id          uuid NOT NULL REFERENCES logs(id) ON DELETE CASCADE
fired_at        timestamptz NOT NULL DEFAULT now()
delivery_status jsonb NOT NULL DEFAULT '{}'::jsonb
                -- e.g. {"webhook": {"status_code": 200, "ms": 87},
                --       "email":   {"ok": true}}

INDEX (rule_id, fired_at DESC)
INDEX (log_id)
```

## Alembic

- Async `env.py` using `async_engine_from_config` + `await connection.run_sync(...)`.
- Initial migration `0001_init.py` creates `pgcrypto` + `citext`, all tables, all indexes.
- API container start command runs migrations before serving:
  ```
  alembic upgrade head && uvicorn llmh.main:app --host 0.0.0.0 --port 8000
  ```
