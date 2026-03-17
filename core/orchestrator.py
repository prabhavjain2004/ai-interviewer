"""
core/orchestrator.py
--------------------
LangGraph state machine — the central nervous system of the platform.

Responsibilities:
- Defines the graph: nodes, edges, conditional phase routing
- Compiles the graph ONCE at app startup (never per-request) — scalability rule
- Provides session lifecycle helpers: init_state, load_state, persist_state
- Wires the Auditor callback into LiveInterviewer
- Triggers Coach agent as a BackgroundTask when status=finished

Rules obeyed:
- Graph compiled once at startup (architecture.md §6)
- All state external in Redis — workers are stateless (architecture.md §6)
- Auditor is parallel, never blocking (rules.md §4)
- Coach runs as BackgroundTask — does not block session close (architecture.md §6)
- Async throughout (rules.md §7)
- No raw dicts between agents — InterviewState is the contract (rules.md §4)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from langgraph.graph import END, StateGraph

from agents.auditor import make_auditor_callback
from agents.interviewer import resolve_next_phase
from core.state import InterviewState
from core.streaming_manager import LiveInterviewer

if TYPE_CHECKING:
    from services.chroma_client import ChromaClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node: sync_state_node
# Lightweight node that syncs LiveInterviewer state into the graph state.
# Called after each audio turn completes.
# ---------------------------------------------------------------------------

async def sync_state_node(state: InterviewState) -> dict:
    """
    Lightweight LangGraph node — only handles phase routing logic.
    Transcript/auditor merging is done BEFORE graph invocation in sync_to_state().
    LangGraph nodes only receive `state` — no extra positional args allowed.
    """
    current_status: str = state.get("status", "warm_up")
    turn_count: int = state.get("turn_count", 0)
    next_phase = resolve_next_phase(current_status, turn_count)
    return {"status": next_phase}


# ---------------------------------------------------------------------------
# Conditional edge: route_after_sync
# Determines next graph node based on interview phase.
# ---------------------------------------------------------------------------

def route_after_sync(state: InterviewState) -> str:
    """
    LangGraph conditional edge function.
    Returns the name of the next node to execute.
    """
    status = state.get("status", "warm_up")
    turn_count = state.get("turn_count", 0)
    next_phase = resolve_next_phase(status, turn_count)

    match next_phase:
        case "finished":
            return "coach_trigger"
        case _:
            return END  # Stay in live loop; next turn will re-enter via sync_state_node


# ---------------------------------------------------------------------------
# Node: coach_trigger_node
# Fires the Coach agent as a background task. Does NOT await it.
# ---------------------------------------------------------------------------

async def coach_trigger_node(state: InterviewState) -> dict:
    """
    Marks the interview as finished and schedules the Coach agent.
    The actual Coach execution happens in agents/coach.py via BackgroundTask.
    This node just sets status=finished and returns — no blocking.
    """
    logger.info(
        "Interview finished | session=%s | total_turns=%d",
        state.get("session_id", "unknown"),
        state.get("turn_count", 0),
    )
    return {"status": "finished"}


# ---------------------------------------------------------------------------
# Graph factory — compiled ONCE at startup
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """
    Builds and compiles the LangGraph StateGraph.
    Called once in main.py at application startup.
    The compiled graph is stored as a module-level singleton and reused per session.

    Node wiring:
        sync_state → [conditional] → coach_trigger | END
        coach_trigger → END
    """
    graph = StateGraph(InterviewState)

    # Nodes — standalone async functions (rules.md §4)
    graph.add_node("sync_state", sync_state_node)
    graph.add_node("coach_trigger", coach_trigger_node)

    # Entry point
    graph.set_entry_point("sync_state")

    # Conditional routing after sync
    graph.add_conditional_edges(
        "sync_state",
        route_after_sync,
        {
            "coach_trigger": "coach_trigger",
            END: END,
        },
    )

    graph.add_edge("coach_trigger", END)

    return graph.compile()


# Module-level compiled graph — set by main.py on startup
_compiled_graph = None


def get_compiled_graph():
    """Returns the module-level compiled graph. Raises if not initialized."""
    if _compiled_graph is None:
        raise RuntimeError(
            "Graph not compiled. Call initialize_graph() in main.py startup."
        )
    return _compiled_graph


def initialize_graph() -> None:
    """Called once in main.py lifespan startup event."""
    global _compiled_graph
    _compiled_graph = build_graph()
    logger.info("LangGraph compiled and ready.")


# ---------------------------------------------------------------------------
# Session lifecycle helpers
# ---------------------------------------------------------------------------

def create_initial_state(
    session_id: str,
    resume_json: dict,
) -> InterviewState:
    """
    Builds the initial InterviewState for a new session.
    Called by api/routes/session.py after resume parsing.
    """
    return InterviewState(
        session_id=session_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        resume_json=resume_json,
        transcript=[],
        auditor_notes=[],
        status="warm_up",
        turn_count=0,
        coach_report=None,
    )


def new_session_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# InterviewSession — per-session runtime object
# Holds LiveInterviewer + auditor sink + state reference for one session.
# ---------------------------------------------------------------------------

class InterviewSession:
    """
    Runtime container for one active interview session.

    Stored in a module-level dict keyed by session_id (in-process only).
    State itself lives in Redis — this object holds the live connection handles.

    On worker restart or scale-out, new workers won't have this object,
    but state is recoverable from Redis. The WebSocket connection would need
    to be re-established (handled by api/websocket.py reconnect logic).
    """

    def __init__(
        self,
        session_id: str,
        resume_json: dict,
        api_key: str,
        chroma_client: "ChromaClient | None" = None,
    ) -> None:
        self.session_id = session_id
        self.api_key = api_key

        self._auditor_notes_sink: list[dict] = []
        self.ws_metadata_sink: list[dict] = []
        self.ws_transcript_sink: list[dict] = []

        auditor_callback = make_auditor_callback(
            resume_json,
            self._auditor_notes_sink,
            self.ws_metadata_sink,
        )

        def transcript_callback(speaker: str, text: str) -> None:
            self.ws_transcript_sink.append({
                "type": "transcript",
                "speaker": speaker,
                "text": text,
            })

        self.live_interviewer = LiveInterviewer(
            session_id=session_id,
            resume_json=resume_json,
            initial_phase="warm_up",
            on_auditor_trigger=auditor_callback,
            on_transcript_event=transcript_callback,
            chroma_client=chroma_client,
        )

    async def start(self) -> None:
        """Opens the Flash Live WebSocket connection."""
        await self.live_interviewer.start(self.api_key)

    async def close(self) -> None:
        """Graceful shutdown of Flash Live connection."""
        await self.live_interviewer.close()

    def drain_auditor_notes(self) -> list[dict]:
        """
        Returns and clears the accumulated auditor notes since last drain.
        Called by the state sync loop to flush notes into Redis.
        """
        notes = list(self._auditor_notes_sink)
        self._auditor_notes_sink.clear()
        return notes

    def drain_ws_metadata(self) -> list[dict]:
        """
        Returns and clears pending real-time auditor metadata + transcript events.
        Called by api/websocket.py send_task on every audio chunk to push to frontend.
        """
        items = list(self.ws_transcript_sink) + list(self.ws_metadata_sink)
        self.ws_transcript_sink.clear()
        self.ws_metadata_sink.clear()
        return items

    async def sync_to_state(self, current_state: InterviewState) -> InterviewState:
        """
        Merges latest LiveInterviewer state into current_state directly.
        Phase routing done inline — no LangGraph invocation on the hot path.
        LangGraph graph is only used at startup for compilation/validation.
        """
        # 1. Merge pending auditor notes
        pending_notes = self.drain_auditor_notes()
        if pending_notes:
            existing = current_state.get("auditor_notes") or []
            current_state["auditor_notes"] = existing + pending_notes

        # 2. Sync transcript + turn count from LiveInterviewer
        current_state["transcript"] = self.live_interviewer.export_transcript()
        current_state["turn_count"] = self.live_interviewer.turn_count

        # 3. Phase routing — inline, no graph invocation needed
        old_phase = current_state.get("status", "warm_up")
        new_phase = resolve_next_phase(old_phase, current_state["turn_count"])
        current_state["status"] = new_phase

        # 4. If phase changed, update Flash Live system_instruction
        if new_phase != old_phase and self.live_interviewer.is_connected:
            await self.live_interviewer.update_phase(new_phase)
            logger.info(
                "Phase transition | session=%s | %s -> %s",
                self.session_id, old_phase, new_phase,
            )

        return current_state


# ---------------------------------------------------------------------------
# In-process session registry
# (stateless workers: this is only for the current process's active WS connections)
# ---------------------------------------------------------------------------

_active_sessions: dict[str, InterviewSession] = {}


def register_session(session: InterviewSession) -> None:
    _active_sessions[session.session_id] = session


def get_session(session_id: str) -> InterviewSession | None:
    return _active_sessions.get(session_id)


def remove_session(session_id: str) -> None:
    _active_sessions.pop(session_id, None)
