from __future__ import annotations

import asyncio

from llmh_worker.redis_consumer import run_forever
from llmh.rule_notifications import run_rule_notification_listener_task, stop_listener_task


async def _main() -> None:
    listener_task, stop_event = await run_rule_notification_listener_task()
    try:
        await run_forever()
    finally:
        await stop_listener_task(listener_task, stop_event)


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
