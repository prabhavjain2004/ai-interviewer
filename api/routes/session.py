"""
api/routes/session.py
---------------------
POST /session/start  — initialise a new interview session
DELETE /session/{id} — close session, trigger coach report as background task
GET /session/{id}/status — lightweight status check
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from agents.coach import run_coach_background
from core.orchestrator import (
    InterviewSession,
    create_initial_state,
    new_session_id,
    register_session,
    remove_session,
    get_session,
)
from core.parser import parse_resume
from services.chroma_client import ChromaClient
from services.redis_client import RedisClient

from api.deps import get_redis, get_chroma, get_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/session", tags=["session"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class StartSessionRequest(BaseModel):
    resume_file_path: str   # Path to already-uploaded resume (set by /resume/upload)


class StartSessionResponse(BaseModel):
    session_id: str
    status: str
    message: str


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    turn_count: int
    has_report: bool


# ---------------------------------------------------------------------------
# POST /session/start
# ---------------------------------------------------------------------------

@router.post("/start", response_model=StartSessionResponse)
async def start_session(
    body: StartSessionRequest,
    redis: RedisClient = Depends(get_redis),
    chroma: ChromaClient = Depends(get_chroma),
    api_key: str = Depends(get_api_key),
) -> StartSessionResponse:
    """
    1. Parse resume → ResumeProfile (Gemini Pro, file deleted after parse).
    2. Embed resume chunks into ChromaDB.
    3. Initialise InterviewState and persist to Redis.
    4. Create InterviewSession (holds LiveInterviewer handle).
    5. Return session_id — client uses this for the WebSocket connection.
    """
    file_path = Path(body.resume_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Resume file not found.")

    session_id = new_session_id()

    try:
        # Parse resume — file deleted inside parse_resume after text extraction
        profile = await parse_resume(file_path, api_key, delete_after_parse=True)
        resume_json = profile.model_dump(mode="json")

        # Embed resume into ChromaDB for RAG
        await chroma.embed_resume(session_id, profile.raw_text)

        # Initialise state and persist to Redis
        state = create_initial_state(session_id, resume_json)
        await redis.save_state(session_id, dict(state))

        # Create session runtime object and register
        session = InterviewSession(
            session_id=session_id,
            resume_json=resume_json,
            api_key=api_key,
        )
        register_session(session)

        logger.info("Session started | session=%s", session_id)
        return StartSessionResponse(
            session_id=session_id,
            status="warm_up",
            message="Session ready. Connect to WebSocket to begin interview.",
        )

    except Exception as exc:
        logger.error("Session start failed | error=%s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# DELETE /session/{session_id}
# ---------------------------------------------------------------------------

@router.delete("/{session_id}")
async def end_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    redis: RedisClient = Depends(get_redis),
    chroma: ChromaClient = Depends(get_chroma),
    api_key: str = Depends(get_api_key),
) -> dict:
    """
    Closes the interview session:
    1. Loads final state from Redis.
    2. Marks status=finished.
    3. Fires Coach report as BackgroundTask (non-blocking).
    4. Closes LiveInterviewer WebSocket.
    5. Removes session from in-process registry.
    """
    state = await redis.load_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    state["status"] = "finished"
    await redis.save_state(session_id, state)

    # Fire Coach as background task — does not block this response
    background_tasks.add_task(run_coach_background, state, api_key, redis)

    # Close Flash Live connection
    session = get_session(session_id)
    if session:
        await session.close()
        remove_session(session_id)

    logger.info("Session ended | session=%s | coach report queued", session_id)
    return {"session_id": session_id, "status": "finished", "message": "Coach report generating."}


# ---------------------------------------------------------------------------
# GET /session/{session_id}/status
# ---------------------------------------------------------------------------

@router.get("/{session_id}/status", response_model=SessionStatusResponse)
async def session_status(
    session_id: str,
    redis: RedisClient = Depends(get_redis),
) -> SessionStatusResponse:
    state = await redis.load_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    has_report = await redis.exists(redis.report_key(session_id))

    return SessionStatusResponse(
        session_id=session_id,
        status=state.get("status", "unknown"),
        turn_count=state.get("turn_count", 0),
        has_report=has_report,
    )
