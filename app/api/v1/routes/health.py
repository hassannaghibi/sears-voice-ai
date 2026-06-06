from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return JSONResponse(
        content={"status": "ok", "version": "1.0.0", "env": settings.app_env}
    )
