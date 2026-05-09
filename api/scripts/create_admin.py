from __future__ import annotations

import argparse
import asyncio

from sqlalchemy.exc import IntegrityError

from llmh.auth.passwords import hash_password
from llmh.db.models import User
from llmh.db.session import AsyncSessionLocal


async def create_admin(username: str, password: str) -> None:
    async with AsyncSessionLocal() as session:
        session.add(User(username=username, password_hash=hash_password(password), role="admin"))
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise SystemExit(f"user already exists: {username}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(create_admin(args.username, args.password))


if __name__ == "__main__":
    main()

