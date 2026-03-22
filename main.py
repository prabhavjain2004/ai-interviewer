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
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.orchestrator import initialize_graph
from services.redis_client import RedisClient
from api.routes import session, resume, report, debug
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
    upstash_redis_rest_url: str
    upstash_redis_rest_token: str
    session_ttl_seconds: int = 86400
    max_turns_warm_up: int = 2      # 2 questions for intro
    max_turns_deep_dive: int = 7    # Cumulative 7 questions (5 deep_dive turns)
    max_turns_stress_test: int = 10 # Cumulative 10 questions (3 stress_test turns)
    allowed_origins: str = "*"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Starting AI Interviewer & Mentor platform...")
    
    Path("data/resumes").mkdir(parents=True, exist_ok=True)
    Path("static").mkdir(exist_ok=True)

    # Upstash Redis
    redis = RedisClient(
        url=settings.upstash_redis_rest_url,
        token=settings.upstash_redis_rest_token,
        ttl=settings.session_ttl_seconds
    )
    await redis.connect()
    app.state.redis = redis

    # Gemini API key — stored on app state, injected via deps.py
    app.state.gemini_api_key = settings.gemini_api_key

    # LangGraph — compiled once, reused per session
    initialize_graph()

    logger.info("All services ready. Platform is live.")
    yield

    # --- Shutdown ---
    await redis.disconnect()
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
    allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(resume.router)
app.include_router(session.router)
app.include_router(report.router)
app.include_router(debug.router)
app.include_router(ws_router)

# Serve static files
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_ui() -> HTMLResponse:
    return HTMLResponse(Path("templates/index.html").read_text(encoding="utf-8"))


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ai-interviewer-mentor"}
