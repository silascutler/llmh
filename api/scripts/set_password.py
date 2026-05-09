from __future__ import annotations

import argparse
import asyncio

from llmh.auth.passwords import hash_password
from llmh.db.models import User
from llmh.db.session import AsyncSessionLocal
from llmh.services.users import get_by_username


async def set_password(username: str, password: str) -> None:
    async with AsyncSessionLocal() as session:
        user = await get_by_username(session, username)
        if user is None:
            raise SystemExit(f"user not found: {username}")

        user.password_hash = hash_password(password)
        session.add(user)
        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(set_password(args.username, args.password))


if __name__ == "__main__":
    main()
