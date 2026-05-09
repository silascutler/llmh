from __future__ import annotations

from fastapi import APIRouter, Response

from llmh.metrics import metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def get_metrics() -> Response:
    return Response(content=metrics.render(), media_type="text/plain; version=0.0.4; charset=utf-8")
