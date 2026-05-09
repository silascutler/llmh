from __future__ import annotations

import time

import httpx


async def send_webhook(url: str, payload: dict) -> dict:
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {"status_code": response.status_code, "ms": elapsed_ms}
