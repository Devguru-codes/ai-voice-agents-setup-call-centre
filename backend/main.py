"""
FastAPI application entry point.

Startup sequence:
  1. Connect Redis
  2. Initialize PostgreSQL (create tables)
  3. Mount all routers

Lifespan handles graceful startup/shutdown.
"""
import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
from memory.database import init_db
from memory.session import session_manager
from api.routes import router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("main")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("🚀 Starting AI Voice Customer Success Platform...")

    # Connect Redis
    try:
        await session_manager.connect()
    except Exception as e:
        logger.error(f"❌ Redis startup failed: {e}")
        # Continue — the app can run without Redis (degraded mode)

    # Initialize PostgreSQL
    try:
        await init_db()
    except Exception as e:
        logger.error(f"❌ Database startup failed: {e}")
        # Continue — will fail on DB queries but won't crash

    logger.info("✅ Server ready")
    yield

    # Shutdown
    logger.info("⏹️ Shutting down...")
    await session_manager.disconnect()
    logger.info("✅ Shutdown complete")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Voice Customer Success Platform",
    description=(
        "Enterprise AI voice agents that join calls, understand customers, "
        "take actions, and update your CRM — automatically."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(router)


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Unhandled exception on {request.method} {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs."},
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=config.DEBUG,
        log_level="debug" if config.DEBUG else "info",
    )
