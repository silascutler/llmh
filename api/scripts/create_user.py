from __future__ import annotations

import argparse
import asyncio

from sqlalchemy.exc import IntegrityError

from llmh.db.session import AsyncSessionLocal
from llmh.services.users import create_user


async def run_create_user(username: str, password: str, role: str) -> None:
    async with AsyncSessionLocal() as session:
        try:
            await create_user(session, username=username, password=password, role=role)
        except IntegrityError as exc:
            raise SystemExit(f"user already exists: {username}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", choices=["admin", "viewer"], default="viewer")
    args = parser.parse_args()
    asyncio.run(run_create_user(args.username, args.password, args.role))


if __name__ == "__main__":
    main()
