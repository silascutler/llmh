from __future__ import annotations

import asyncio

from llmh.db.session import AsyncSessionLocal
from llmh.services.users import list_users


async def run_list_users() -> None:
    async with AsyncSessionLocal() as session:
        users = await list_users(session)
        for user in users:
            print(f"{user.username}\t{user.role}\t{user.created_at.isoformat()}")


def main() -> None:
    asyncio.run(run_list_users())


if __name__ == "__main__":
    main()
