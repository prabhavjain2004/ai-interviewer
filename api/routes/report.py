"""
api/routes/report.py
--------------------
GET /report/{session_id} — retrieve the Mirror & Mentor coaching report.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from services.redis_client import RedisClient
from api.deps import get_redis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/report", tags=["report"])


@router.get("/{session_id}")
async def get_report(
    session_id: str,
    redis: RedisClient = Depends(get_redis),
) -> dict:
    """
    Returns the CoachReport JSON for a completed session.
    Returns 202 if the report is still being generated.
    Returns 404 if the session doesn't exist.
    """
    # Check session exists
    state = await redis.load_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Check report is ready
    report = await redis.load_report(session_id)
    if not report:
        status = state.get("status", "unknown")
        if status != "finished":
            raise HTTPException(
                status_code=400,
                detail=f"Interview not finished yet. Current status: {status}",
            )
        # Finished but report not ready yet — still generating
        raise HTTPException(
            status_code=202,
            detail="Report is being generated. Please retry in a few seconds.",
        )

    logger.info("Report retrieved | session=%s", session_id)
    return report
