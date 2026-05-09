from __future__ import annotations

import argparse
import asyncio

from llmh.auth.reset_tokens import create_reset_token
from llmh.db.session import AsyncSessionLocal
from llmh.services.users import get_by_username


async def run_create_reset_token(username: str, base_url: str | None, print_url: bool) -> None:
    async with AsyncSessionLocal() as session:
        user = await get_by_username(session, username)
        if user is None:
            raise SystemExit(f"user not found: {username}")
        token = create_reset_token(user)
        print(f"token={token}")
        if base_url and print_url:
            normalized_base = base_url.rstrip("/")
            print(f"url={normalized_base}/reset-password?token={token}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--base-url")
    parser.add_argument("--print-url", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_create_reset_token(args.username, args.base_url, args.print_url))


if __name__ == "__main__":
    main()
