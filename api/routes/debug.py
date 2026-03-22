"""
api/routes/debug.py
-------------------
Debug endpoints for troubleshooting report generation issues.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from services.redis_client import RedisClient
from api.deps import get_redis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/session/{session_id}")
async def debug_session(
    session_id: str,
    redis: RedisClient = Depends(get_redis),
) -> dict:
    """
    Returns full session state for debugging.
    Shows transcript, status, turn count, etc.
    """
    state = await redis.load_state(session_id)
    if not state:
        return {"error": "Session not found"}
    
    report = await redis.load_report(session_id)
    
    transcript = state.get("transcript", [])
    student_turns = [t for t in transcript if t.get("speaker") == "student"]
    interviewer_turns = [t for t in transcript if t.get("speaker") == "interviewer"]
    
    return {
        "session_id": session_id,
        "status": state.get("status"),
        "turn_count": state.get("turn_count"),
        "transcript_total": len(transcript),
        "transcript_student": len(student_turns),
        "transcript_interviewer": len(interviewer_turns),
        "has_report": report is not None,
        "report_exists": report is not None,
        "transcript_preview": transcript[:3] if transcript else [],
        "auditor_notes_count": len(state.get("auditor_notes", [])),
        "resume_exists": bool(state.get("resume_json")),
    }
