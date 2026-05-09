from __future__ import annotations

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from llmh.auth.client_ip import get_client_ip
from llmh.config import get_settings


async def _redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


async def enforce_rate_limit(
    request: Request,
    *,
    bucket: str,
    limit: int,
    window_seconds: int,
) -> None:
    client_ip = get_client_ip(request)
    key = f"llmh:rate-limit:{bucket}:{client_ip}"
    redis = await _redis_client()
    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)
        if count > limit:
            ttl = await redis.ttl(key)
            retry_after = ttl if ttl > 0 else window_seconds
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="too many requests",
                headers={"Retry-After": str(retry_after)},
            )
    finally:
        await redis.aclose()
