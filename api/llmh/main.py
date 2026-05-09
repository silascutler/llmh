from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from llmh.config import get_settings
from llmh.metrics import metrics
from llmh.routers import alerts, auth, health, ingest, logs, metrics as metrics_router, rules, sources
from llmh.rule_notifications import run_rule_notification_listener_task, stop_listener_task
from llmh.search.index import ensure_index


@asynccontextmanager
async def lifespan(_: FastAPI):
    await ensure_index()
    listener_task, stop_event = await run_rule_notification_listener_task()
    try:
        yield
    finally:
        await stop_listener_task(listener_task, stop_event)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="llmh", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="llmh_session",
        max_age=14 * 24 * 60 * 60,
        same_site="lax",
        https_only=settings.session_https_only,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def capture_metrics(request: Request, call_next):
        response = await call_next(request)
        metrics.inc(
            "http_requests_total",
            method=request.method,
            path=request.url.path,
            status_code=str(response.status_code),
        )
        return response

    app.include_router(auth.router)
    app.include_router(ingest.router)
    app.include_router(logs.router)
    app.include_router(rules.router)
    app.include_router(alerts.router)
    app.include_router(sources.router)
    app.include_router(health.router)
    app.include_router(metrics_router.router)
    return app


app = create_app()
