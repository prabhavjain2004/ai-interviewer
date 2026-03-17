"""
main.py
-------
FastAPI application entry point.

Startup sequence:
1. Load settings from environment (pydantic-settings).
2. Connect Redis and ChromaDB.
3. Compile LangGraph graph (once — reused per session).
4. Mount all routers.

Shutdown sequence:
1. Disconnect Redis and ChromaDB.

Rules obeyed:
- LangGraph compiled once at startup (architecture.md §6)
- Async lifespan (rules.md §7)
- Settings via pydantic-settings — no hardcoded keys (rules.md §7)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.orchestrator import initialize_graph
from services.redis_client import RedisClient
from services.chroma_client import ChromaClient
from api.routes import session, resume, report
from api.websocket import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    gemini_api_key: str
    redis_url: str = "redis://localhost:6379"
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    session_ttl_seconds: int = 86400
    max_turns_warm_up: int = 3
    max_turns_deep_dive: int = 5
    max_turns_stress_test: int = 3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Starting AI Interviewer & Mentor platform...")

    # Redis
    redis = RedisClient(url=settings.redis_url, ttl=settings.session_ttl_seconds)
    await redis.connect()
    app.state.redis = redis

    # ChromaDB
    chroma = ChromaClient(host=settings.chroma_host, port=settings.chroma_port)
    chroma.connect()
    app.state.chroma = chroma

    # Gemini API key — stored on app state, injected via deps.py
    app.state.gemini_api_key = settings.gemini_api_key

    # LangGraph — compiled once, reused per session
    initialize_graph()

    logger.info("All services ready. Platform is live.")
    yield

    # --- Shutdown ---
    await redis.disconnect()
    chroma.disconnect()
    logger.info("Platform shutdown complete.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Technical Interviewer & Mentor",
    description="Ribbon.ai-killer: sub-500ms Gemini Live interviews with Mirror & Mentor coaching.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(resume.router)
app.include_router(session.router)
app.include_router(report.router)
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ai-interviewer-mentor"}
