# llmh — Documentation

`llmh` is a self-hosted web app for archiving, searching, and alerting on logs emitted by CLI LLM tools (Claude Code, Codex, Aider, etc.) running across one or more developer machines. The goal of this platform is to preserve chat histories and associated machines and context.

Each emitting machine is registered as a **Source**. Logs flow in via **HTTP POST** or **Redis Streams**, are persisted in **Postgres** (source of truth), mirrored into **Meilisearch** for full-text search, and evaluated against user-defined **AlertRules**. Rule matches fire **webhooks** and/or **email** and are recorded as **AlertEvents**. A **Next.js** UI sits on top of a FastAPI REST backend. The full stack runs under Docker Compose.

End-to-end loop is proven by `client/`, a standalone Python CLI (`llmh-client`) that scans Claude project archives and Codex rollout sessions and uploads them to `/ingest`.

## Documentation Index

| Doc | Contents |
|---|---|
| [architecture.md](architecture.md) | Locked tech stack, repo layout, backend module responsibilities, library pins |
| [data-model.md](data-model.md) | Postgres schema (sources, logs, users, alert rules, alert events) |
| [ingestion.md](ingestion.md) | HTTP `POST /ingest` + Redis Streams worker |
| [search.md](search.md) | Meilisearch index config, sync strategy, `GET /logs` search API |
| [api.md](api.md) | Sources, auth, and alerts REST endpoints |
| [alerts.md](alerts.md) | Rule evaluation, webhook + email delivery |
| [frontend.md](frontend.md) | Next.js routes, components, auth gate |
| [deployment.md](deployment.md) | Docker Compose, env vars, end-to-end verification |
| [phases.md](phases.md) | Ordered implementation phases for the coding agent |

## Quick Reference

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.x async, Pydantic v2
- **Storage**: PostgreSQL 16 (truth) + Meilisearch (search index)
- **Ingestion**: HTTP + Redis Streams
- **Auth**: Shared bearer token for ingest; argon2 username/password sessions for UI
- **Alerts**: Rule-based, webhook + email
- **Frontend**: Next.js 15 + TypeScript + Tailwind + shadcn/ui
- **Deploy**: Docker Compose (`api`, `worker`, `web`, `postgres`, `redis`, `meilisearch`)

## Build Order

Implement in the order described in [phases.md](phases.md). Each phase ends in a runnable, testable state.
