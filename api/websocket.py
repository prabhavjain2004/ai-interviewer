"""
api/websocket.py
----------------
WS /interview/{session_id} — bidirectional audio bridge between browser and Flash Live.

Protocol:
  Browser → Server: raw PCM audio bytes (16kHz, mono, 16-bit)
  Server  → Browser: raw PCM audio bytes (AI voice response)
  Server  → Browser: JSON text frames (transcript, auditor metadata, status)
  Browser → Server: text "END_INTERVIEW" to close gracefully

Refinements implemented:
1. Real-time auditor metadata pushed as JSON text frames (heatmap data for frontend)
2. 60-second reconnect buffer — temporary disconnect does NOT trigger Coach agent
3. State persisted to Redis on every turn so reconnect resumes cleanly
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.orchestrator import get_session, remove_session
from services.redis_client import RedisClient
from agents.coach import run_coach_background

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

SYNC_EVERY_N_TURNS = 2
RECONNECT_WINDOW_SECONDS = 60  # Grace period before session is considered dead


# ---------------------------------------------------------------------------
# Reconnect buffer registry
# session_id → timestamp of disconnect (UTC)
# If student reconnects within RECONNECT_WINDOW_SECONDS, session resumes.
# ---------------------------------------------------------------------------
_disconnect_timestamps: dict[str, datetime] = {}


def _record_disconnect(session_id: str) -> None:
    _disconnect_timestamps[session_id] = datetime.now(timezone.utc)


def _clear_disconnect(session_id: str) -> None:
    _disconnect_timestamps.pop(session_id, None)


def _is_within_reconnect_window(session_id: str) -> bool:
    ts = _disconnect_timestamps.get(session_id)
    if ts is None:
        return False
    elapsed = (datetime.now(timezone.utc) - ts).total_seconds()
    return elapsed <= RECONNECT_WINDOW_SECONDS


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------

@router.websocket("/interview/{session_id}")
async def interview_websocket(
    websocket: WebSocket,
    session_id: str,
) -> None:
    app = websocket.app
    redis: RedisClient = app.state.redis
    api_key: str = app.state.gemini_api_key

    await websocket.accept()

    # --- Reconnect check ---
    reconnecting = _is_within_reconnect_window(session_id)
    if reconnecting:
        _clear_disconnect(session_id)
        logger.info("WebSocket reconnected within window | session=%s", session_id)
    else:
        logger.info("WebSocket connected | session=%s", session_id)

    session = get_session(session_id)
    if not session:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Session not found. Call POST /session/start first."
        }))
        await websocket.close(code=4004)
        return

    state = await redis.load_state(session_id)
    if not state:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Session state not found in Redis."
        }))
        await websocket.close(code=4004)
        return

    # On reconnect, don't re-open Flash Live if already connected
    if not session.live_interviewer.is_connected:
        try:
            await session.start()
        except Exception as exc:
            logger.error("Flash Live connection failed | session=%s | error=%s", session_id, exc)
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Could not connect to Gemini Live: {exc}"
            }))
            await websocket.close(code=1011)
            return

    # Send current status to client on connect/reconnect
    await websocket.send_text(json.dumps({
        "type": "status",
        "phase": state.get("status", "warm_up"),
        "turn_count": state.get("turn_count", 0),
    }))

    turn_counter = [0]
    ended_cleanly = [False]
    _sync_lock = asyncio.Lock()   # prevent concurrent sync_to_state calls

    async def _persist_state() -> None:
        nonlocal state
        if _sync_lock.locked():
            return  # skip if a sync is already in progress
        async with _sync_lock:
            try:
                state = await session.sync_to_state(state)
                await redis.save_state(session_id, dict(state))
            except Exception as exc:
                logger.warning("State sync failed | session=%s | error=%s", session_id, exc)

    # ------------------------------------------------------------------
    # Task A: Browser mic → Flash Live
    # ------------------------------------------------------------------
    async def receive_task() -> None:
        try:
            while True:
                message = await websocket.receive()
                msg_bytes = message.get("bytes")
                msg_text = message.get("text")

                if msg_bytes is not None:
                    await session.live_interviewer.send_audio(msg_bytes)
                elif msg_text is not None:
                    text = msg_text.strip()
                    control = text.upper()
                    if control == "END_INTERVIEW":
                        ended_cleanly[0] = True
                        logger.info("END_INTERVIEW received | session=%s", session_id)
                        return
                    elif control == "TURN_COMPLETE":
                        await session.live_interviewer.signal_activity_end()
                        logger.debug("TURN_COMPLETE handled (manual VAD mode) | session=%s", session_id)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected | session=%s", session_id)
        except Exception as exc:
            logger.warning("receive_task error | session=%s | error=%s", session_id, exc)

    # ------------------------------------------------------------------
    # Task B: Flash Live → browser (audio + metadata)
    # ------------------------------------------------------------------
    async def send_task() -> None:
        last_synced_turn = state.get("turn_count", 0)
        try:
            async for event in session.live_interviewer.stream_response():
                # Send AI audio bytes to browser (event may be None on non-audio turn complete)
                if event:
                    await websocket.send_bytes(event)

                # Drain and push real-time auditor metadata (heatmap data)
                for meta in session.drain_ws_metadata():
                    try:
                        await websocket.send_text(json.dumps(meta))
                    except Exception:
                        pass

                # Persist and notify status whenever a full turn completes,
                # even if that turn produced no audio bytes.
                current_turn = session.live_interviewer.turn_count
                if current_turn != last_synced_turn:
                    last_synced_turn = current_turn
                    await _persist_state()
                    try:
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "phase": state.get("status", "warm_up"),
                            "turn_count": state.get("turn_count", current_turn),
                        }))
                    except Exception:
                        pass

            # stream_response() exhausted = Live session closed server-side
            logger.info("Flash Live stream ended | session=%s", session_id)

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.warning("send_task error | session=%s | error=%s", session_id, exc)

    # ------------------------------------------------------------------
    # Run both tasks concurrently
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
        if ended_cleanly[0]:
            # Clean intentional end — close Flash Live, final state persist, trigger coach
            await session.close()
            try:
                state = await session.sync_to_state(state)
                state["status"] = "finished"
                await redis.save_state(session_id, dict(state))
                logger.info("Session ended cleanly | session=%s | turns=%d",
                            session_id, state.get("turn_count", 0))
                
                # Trigger coach report AFTER transcript is confirmed in Redis
                asyncio.create_task(
                    _run_coach_safe(state, api_key, redis),
                    name=f"coach-{session_id}",
                )
                logger.info("Coach report triggered after transcript persist | session=%s", session_id)
            except Exception as exc:
                logger.warning("Final state sync failed | session=%s | error=%s", session_id, exc)
            remove_session(session_id)
        else:
            # Unexpected disconnect — record timestamp, keep session alive for reconnect window
            _record_disconnect(session_id)
            # Persist state so reconnect can resume
            try:
                state = await session.sync_to_state(state)
                await redis.save_state(session_id, dict(state))
                logger.info(
                    "Disconnect recorded — reconnect window open for %ds | session=%s",
                    RECONNECT_WINDOW_SECONDS, session_id,
                )
            except Exception as exc:
                logger.warning("State persist on disconnect failed | session=%s | error=%s",
                               session_id, exc)

            # Schedule session cleanup after reconnect window expires
            asyncio.create_task(
                _cleanup_after_window(session_id, RECONNECT_WINDOW_SECONDS, api_key, redis, app.state.chroma),
                name=f"cleanup-{session_id}",
            )

        try:
            await websocket.close()
        except Exception:
            pass


async def _cleanup_after_window(session_id: str, delay: int, api_key: str, redis: RedisClient, chroma) -> None:
    """
    Waits for the reconnect window to expire.
    If the student did NOT reconnect, triggers the Coach report and cleans up.
    """
    await asyncio.sleep(delay)
    if _is_within_reconnect_window(session_id):
        return
    if session_id in _disconnect_timestamps:
        _disconnect_timestamps.pop(session_id, None)
        session = get_session(session_id)
        if session:
            await session.close()
            remove_session(session_id)
        await chroma.delete_session_collection(session_id)

        # Trigger coach report — session ended without END_INTERVIEW
        state = await redis.load_state(session_id)
        if state and state.get("turn_count", 0) > 0:
            state["status"] = "finished"
            await redis.save_state(session_id, state)
            asyncio.create_task(
                _run_coach_safe(state, api_key, redis),
                name=f"coach-{session_id}",
            )
            logger.info("Coach triggered after reconnect window expired | session=%s", session_id)
        else:
            logger.info("Session cleaned up after reconnect window expired | session=%s", session_id)


async def _run_coach_safe(state: dict, api_key: str, redis: RedisClient) -> None:
    try:
        await run_coach_background(state, api_key, redis)
    except Exception as exc:
        logger.warning("Coach background task failed | session=%s | error=%s",
                       state.get("session_id", "?"), exc)
