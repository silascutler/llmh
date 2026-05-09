from __future__ import annotations

import asyncio
from contextlib import suppress

import asyncpg
from sqlalchemy import text

from llmh.alerts.evaluator import clear_rule_cache
from llmh.config import get_settings

CHANNEL = "alert_rules_changed"


def _asyncpg_dsn() -> str:
    database_url = get_settings().database_url
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


async def notify_rules_changed() -> None:
    from llmh.db.session import engine

    async with engine.begin() as connection:
        await connection.execute(text("SELECT pg_notify(:channel, 'changed')"), {"channel": CHANNEL})


class RuleNotificationListener:
    def __init__(self) -> None:
        self._connection: asyncpg.Connection | None = None
        self._ready = asyncio.Event()
        self._closed = False

    async def start(self) -> None:
        self._connection = await asyncpg.connect(_asyncpg_dsn())

        def _handle_notification(*_: object) -> None:
            clear_rule_cache()

        await self._connection.add_listener(CHANNEL, _handle_notification)
        clear_rule_cache()
        self._ready.set()

    async def wait_until_ready(self) -> None:
        await self._ready.wait()

    async def stop(self) -> None:
        self._closed = True
        if self._connection is not None:
            await self._connection.close()
            self._connection = None


async def run_rule_notification_listener(stop_event: asyncio.Event) -> None:
    listener = RuleNotificationListener()
    await listener.start()
    try:
        await stop_event.wait()
    finally:
        await listener.stop()


async def run_rule_notification_listener_task() -> tuple[asyncio.Task[None], asyncio.Event]:
    stop_event = asyncio.Event()
    task = asyncio.create_task(run_rule_notification_listener(stop_event))
    await asyncio.sleep(0)
    return task, stop_event


async def stop_listener_task(task: asyncio.Task[None], stop_event: asyncio.Event) -> None:
    stop_event.set()
    with suppress(asyncio.CancelledError):
        await task
