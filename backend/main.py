"""
FastAPI application entry point.
"""
from __future__ import annotations

import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database.connection import init_db
from scheduler.scheduler import start_scheduler, stop_scheduler

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("startup", app=settings.APP_NAME, env=settings.APP_ENV)

    # Init database tables (dev only — use Alembic in production)
    await init_db()

    # Start background scheduler
    start_scheduler()

    yield

    # Cleanup
    stop_scheduler()
    logger.info("shutdown")


# ─── App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description="Secure & Intelligent Agentic RAG Platform for Educational Environments",
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
    lifespan=lifespan,
)

# ─── CORS ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routes ─────────────────────────────────────────────────────────────
from api.v1.auth import router as auth_router
from api.v1.documents import router as docs_router
from api.v1.chat import router as chat_router
from api.v1.analysis import router as analysis_router
from api.v1.deadlines import router as deadlines_router
from api.v1.admin import router as admin_router

API_PREFIX = "/api/v1"
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(docs_router, prefix=API_PREFIX)
app.include_router(chat_router, prefix=API_PREFIX)
app.include_router(analysis_router, prefix=API_PREFIX)
app.include_router(deadlines_router, prefix=API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX)


# ─── Health Check ───────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}


# ─── Global error handler ───────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )
