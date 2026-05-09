from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from llmh.config import get_settings
from llmh.db.session import get_session

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    settings = get_settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{settings.meili_url}/health", headers={"Authorization": f"Bearer {settings.meili_master_key}"})
        response.raise_for_status()
    return {"status": "ok"}

