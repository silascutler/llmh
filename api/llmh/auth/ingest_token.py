from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from llmh.config import get_settings


def validate_ingest_bearer_token(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    expected = get_settings().ingest_bearer_token
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token")


async def require_ingest_token(authorization: str | None = Header(default=None, alias="Authorization")) -> None:
    validate_ingest_bearer_token(authorization)
