from __future__ import annotations

import argparse
import asyncio

from llmh.db.session import AsyncSessionLocal
from llmh.services.users import delete_user, get_by_username


async def run_delete_user(username: str) -> None:
    async with AsyncSessionLocal() as session:
        user = await get_by_username(session, username)
        if user is None:
            raise SystemExit(f"user not found: {username}")
        try:
            await delete_user(session, user)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    asyncio.run(run_delete_user(args.username))


if __name__ == "__main__":
    main()
