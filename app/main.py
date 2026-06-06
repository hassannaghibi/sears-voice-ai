from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import NotFoundError, SlotNotAvailableError
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", env=settings.app_env, base_url=settings.base_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("database_connected")
    except Exception as exc:
        logger.warning("database_connect_skipped", reason=str(exc))
    yield
    logger.info("shutdown")
    await engine.dispose()


app = FastAPI(
    title="Sears Home Services Voice AI",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [settings.base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


# Global exception handlers
@app.exception_handler(SlotNotAvailableError)
async def slot_not_available_handler(request: Request, exc: SlotNotAvailableError):
    return JSONResponse(
        status_code=409,
        content={"code": "slot_not_available", "message": str(exc)},
    )


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"code": "not_found", "message": str(exc)},
    )


# Routers
from app.api.v1.routes import appointments, health, technicians, voice  # noqa: E402

app.include_router(health.router)
app.include_router(technicians.router, prefix="/api/v1")
app.include_router(appointments.router, prefix="/api/v1")
app.include_router(voice.router)
