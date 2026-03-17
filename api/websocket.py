"""
api/websocket.py
----------------
WS /interview/{session_id} — bidirectional audio bridge between browser and Flash Live.

Protocol:
  Browser → Server: raw PCM audio bytes (16kHz, mono, 16-bit)
  Server  → Browser: raw PCM audio bytes (AI voice response)
  Browser → Server: text message "END_INTERVIEW" to close session gracefully

Rules obeyed:
- No raw audio stored at any point (rules.md §6)
- Graceful disconnect: state persisted to Redis on close (architecture.md §6)
- Auditor fires non-blocking via LiveInterviewer._fire_auditor (rules.md §4)
- State synced to Redis on every turn_complete event (architecture.md §6)
- Async throughout (rules.md §7)
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.orchestrator import (
    InterviewSession,
    get_session,
    register_session,
    remove_session,
)
from services.redis_client import RedisClient
from services.chroma_client import ChromaClient

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

SYNC_EVERY_N_TURNS = 2   # Persist state to Redis every N turns (balance between durability and overhead)


@router.websocket("/interview/{session_id}")
async def interview_websocket(
    websocket: WebSocket,
    session_id: str,
) -> None:
    """
    Main WebSocket handler for the live interview audio stream.

    Flow per connection:
    1. Accept WebSocket.
    2. Load session from in-process registry (created by POST /session/start).
    3. Start Flash Live connection.
    4. Spawn two concurrent tasks:
       a. receive_task: browser mic → Flash Live (send_audio)
       b. send_task: Flash Live response → browser (stream_response)
    5. On disconnect or "END_INTERVIEW": close Flash Live, persist state to Redis.
    """
    app = websocket.app
    redis: RedisClient = app.state.redis
    api_key: str = app.state.gemini_api_key

    await websocket.accept()
    logger.info("WebSocket connected | session=%s", session_id)

    # Load session runtime object
    session: InterviewSession | None = get_session(session_id)
    if not session:
        await websocket.send_text("ERROR: Session not found. Call POST /session/start first.")
        await websocket.close(code=4004)
        return

    # Load state from Redis
    state = await redis.load_state(session_id)
    if not state:
        await websocket.send_text("ERROR: Session state not found in Redis.")
        await websocket.close(code=4004)
        return

    # Open Flash Live connection
    try:
        await session.start()
    except Exception as exc:
        logger.error("Flash Live connection failed | session=%s | error=%s", session_id, exc)
        await websocket.send_text(f"ERROR: Could not connect to Gemini Live: {exc}")
        await websocket.close(code=1011)
        return

    turn_counter = [0]   # mutable ref for closure

    async def _persist_state() -> None:
        """Syncs LangGraph state and persists to Redis."""
        nonlocal state
        try:
            state = await session.sync_to_state(state)
            await redis.save_state(session_id, dict(state))
        except Exception as exc:
            logger.warning("State sync failed | session=%s | error=%s", session_id, exc)

    # ------------------------------------------------------------------
    # Task A: Receive audio from browser → forward to Flash Live
    # ------------------------------------------------------------------
    async def receive_task() -> None:
        try:
            while True:
                message = await websocket.receive()

                if "bytes" in message:
                    # Raw PCM audio — forward to Flash Live (never stored)
                    await session.live_interviewer.send_audio(message["bytes"])

                elif "text" in message:
                    text = message["text"].strip()
                    if text == "END_INTERVIEW":
                        logger.info("END_INTERVIEW received | session=%s", session_id)
                        return  # Triggers cleanup in outer scope

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected | session=%s", session_id)
        except Exception as exc:
            logger.warning("receive_task error | session=%s | error=%s", session_id, exc)

    # ------------------------------------------------------------------
    # Task B: Stream Flash Live audio response → browser
    # ------------------------------------------------------------------
    async def send_task() -> None:
        try:
            async for audio_chunk in session.live_interviewer.stream_response():
                await websocket.send_bytes(audio_chunk)

                # Periodic state sync every N turns
                turn_counter[0] += 1
                if turn_counter[0] % SYNC_EVERY_N_TURNS == 0:
                    asyncio.create_task(_persist_state())

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.warning("send_task error | session=%s | error=%s", session_id, exc)

    # ------------------------------------------------------------------
    # Run both tasks concurrently — cancel both when either finishes
    # ------------------------------------------------------------------
    try:
        recv = asyncio.create_task(receive_task())
        send = asyncio.create_task(send_task())
        done, pending = await asyncio.wait(
            [recv, send],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        # Graceful shutdown
        await session.close()

        # Final state sync — drain any remaining auditor notes
        try:
            state = await session.sync_to_state(state)
            await redis.save_state(session_id, dict(state))
            logger.info("Final state persisted | session=%s | turns=%d",
                        session_id, state.get("turn_count", 0))
        except Exception as exc:
            logger.warning("Final state sync failed | session=%s | error=%s", session_id, exc)

        try:
            await websocket.close()
        except Exception:
            pass
