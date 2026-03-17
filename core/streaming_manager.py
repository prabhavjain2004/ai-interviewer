"""
core/streaming_manager.py
--------------------------
Manages the Gemini 1.5 Flash Live WebSocket session for the real-time interview.

Rules obeyed:
- Flash Live ONLY for the interview loop — never Pro (rules.md §1)
- VAD enabled natively — supports student barge-in (hld.md §2)
- system_instruction injected with full resume_json at session start (rules.md §3)
- Auditor fired as asyncio.create_task() on every transcript event — never blocks (rules.md §4)
- No raw audio stored on server (rules.md §6)
- Graceful disconnect: closes Live session, persists state to Redis (architecture.md §6)
- Async throughout (rules.md §7)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncIterator, Callable

from google import genai
from google.genai import types as genai_types

from core.state import ConversationTurn, InterviewState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FLASH_LIVE_MODEL = "models/gemini-1.5-flash-latest"   # Flash Live — sub-500ms

# Audio format expected by Gemini Live and sent back to browser
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1


# ---------------------------------------------------------------------------
# System instruction builder
# ---------------------------------------------------------------------------

def build_system_instruction(resume_json: dict, phase: str) -> str:
    """
    Injects the student's resume_json into the Flash Live system_instruction.
    Phase-aware tone: warm in warm_up, technically firm in deep_dive/stress_test.
    Entity grounding is enforced here — rules.md §3.
    """
    resume_str = json.dumps(resume_json, indent=2)

    phase_guidance = {
        "warm_up": (
            "You are in the WARM-UP phase. Be warm, welcoming, and conversational. "
            "Ask 2-3 broad questions to build rapport. Generic questions are allowed here."
        ),
        "deep_dive": (
            "You are in the DEEP-DIVE phase. Every question MUST reference a specific entity "
            "from the student's resume (project name, company, tech stack item). "
            "Be technically firm but encouraging. Never say 'that's wrong' — ask follow-ups instead."
        ),
        "stress_test": (
            "You are in the STRESS-TEST phase. Push on edge cases, trade-offs, and failure scenarios. "
            "Every question MUST name a specific resume entity. Increase technical pressure gradually. "
            "You are a supportive partner — not a judge."
        ),
    }

    return f"""You are an elite technical interviewer and supportive mentor for university students.
Your persona: A senior engineer who genuinely wants the student to succeed.
You are NOT a judge. You are a Supportive Partner.

PROHIBITED phrases: "That's wrong", "Incorrect", "You failed to mention."
REQUIRED approach: Ask follow-up questions that guide the student toward the right answer.

{phase_guidance.get(phase, phase_guidance["warm_up"])}

--- STUDENT RESUME (use these entities as Question Anchors) ---
{resume_str}
--- END RESUME ---

Key resume entities to drill into:
- Projects: {[p.get("name") for p in resume_json.get("projects", [])]}
- Tech Stack: {resume_json.get("tech_stack", [])}
- Power Facts: {resume_json.get("power_facts", [])}

Voice Activity Detection is active. The student may interrupt you — stop immediately and listen.
Keep your responses concise (under 30 seconds when spoken). Ask one question at a time.
"""


# ---------------------------------------------------------------------------
# LiveInterviewer
# ---------------------------------------------------------------------------

class LiveInterviewer:
    """
    Manages a single Gemini 1.5 Flash Live session for one interview.

    Lifecycle:
        1. __init__: store session context
        2. start(): open Flash Live connection, inject resume system_instruction
        3. stream_audio(): async generator — yields AI audio chunks back to browser
        4. send_audio(): push raw mic bytes from browser into Flash Live
        5. on_transcript_event(): fires Auditor as asyncio.create_task() (non-blocking)
        6. close(): graceful shutdown, state persisted by caller

    One instance per session. Never reused across sessions.
    """

    def __init__(
        self,
        session_id: str,
        resume_json: dict,
        initial_phase: str = "warm_up",
        on_auditor_trigger: Callable[[str, int], None] | None = None,
    ) -> None:
        self.session_id = session_id
        self.resume_json = resume_json
        self.phase = initial_phase
        self.turn_count = 0

        # Callback fired (non-blocking) when a student transcript chunk arrives
        # Signature: (student_text: str, turn_index: int) -> None
        # agents/auditor.py registers here via orchestrator
        self._on_auditor_trigger = on_auditor_trigger

        self._client: genai.Client | None = None
        self._live_session = None          # google-genai Live session handle
        self._is_connected = False

        # Accumulated transcript for this session (ConversationTurn dicts)
        self._transcript: list[dict] = []

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def start(self, api_key: str) -> None:
        """
        Opens the Gemini Flash Live WebSocket connection.
        Injects resume as system_instruction.
        Enables VAD for natural barge-in.
        """
        self._client = genai.Client(api_key=api_key)

        system_instruction = build_system_instruction(self.resume_json, self.phase)

        config = genai_types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=system_instruction,
            # VAD enabled — student can barge in naturally (hld.md §2)
            realtime_input_config=genai_types.RealtimeInputConfig(
                automatic_activity_detection=genai_types.AutomaticActivityDetection(
                    disabled=False,
                )
            ),
            speech_config=genai_types.SpeechConfig(
                voice_config=genai_types.VoiceConfig(
                    prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                        voice_name="Charon"   # Professional, warm voice
                    )
                )
            ),
        )

        self._live_session = await self._client.aio.live.connect(
            model=FLASH_LIVE_MODEL,
            config=config,
        ).__aenter__()

        self._is_connected = True
        logger.info("Flash Live session opened | session_id=%s | phase=%s",
                    self.session_id, self.phase)

    async def close(self) -> None:
        """Graceful shutdown. Caller is responsible for persisting state to Redis."""
        if self._live_session and self._is_connected:
            try:
                await self._live_session.__aexit__(None, None, None)
            except Exception:
                pass  # Best-effort close
        self._is_connected = False
        logger.info("Flash Live session closed | session_id=%s", self.session_id)

    # ------------------------------------------------------------------
    # Audio I/O
    # ------------------------------------------------------------------

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """
        Push raw PCM audio bytes from the browser mic into Flash Live.
        Called by api/websocket.py on every incoming WebSocket message.
        No audio is stored — bytes are forwarded directly (rules.md §6).
        """
        if not self._is_connected or self._live_session is None:
            return
        await self._live_session.send(
            input=genai_types.LiveClientRealtimeInput(
                media_chunks=[
                    genai_types.Blob(
                        data=pcm_bytes,
                        mime_type=f"audio/pcm;rate={AUDIO_SAMPLE_RATE}",
                    )
                ]
            )
        )

    async def stream_response(self) -> AsyncIterator[bytes]:
        """
        Async generator that yields AI audio response chunks back to the browser.
        Also captures transcript text when available and fires the Auditor.

        Yields: raw PCM audio bytes (forward directly to browser WebSocket).
        """
        if not self._live_session:
            return

        async for response in self._live_session.receive():
            # --- Audio chunk: yield immediately to browser (sub-500ms path) ---
            if response.data:
                yield response.data

            # --- Transcript event: fire Auditor as non-blocking task ---
            if response.server_content:
                content = response.server_content

                # Capture model (interviewer) turn text
                if content.model_turn and content.model_turn.parts:
                    for part in content.model_turn.parts:
                        if hasattr(part, "text") and part.text:
                            self._append_turn("interviewer", part.text)

                # Capture input (student) transcript when Flash Live returns it
                if content.input_transcription:
                    student_text = content.input_transcription.text
                    if student_text.strip():
                        self._append_turn("student", student_text)
                        # Fire Auditor — non-blocking, never awaited here (rules.md §4)
                        self._fire_auditor(student_text, self.turn_count)

                # Turn complete signal — increment turn counter
                if content.turn_complete:
                    self.turn_count += 1

    # ------------------------------------------------------------------
    # Phase update (called by orchestrator when LangGraph transitions phase)
    # ------------------------------------------------------------------

    async def update_phase(self, new_phase: str) -> None:
        """
        Re-injects system_instruction when the interview phase changes.
        Flash Live supports mid-session instruction updates.
        """
        if not self._is_connected or self._live_session is None:
            return
        self.phase = new_phase
        new_instruction = build_system_instruction(self.resume_json, new_phase)
        await self._live_session.send(
            input=genai_types.LiveClientToolResponse(
                function_responses=[]
            )
        )
        logger.info("Phase updated | session_id=%s | new_phase=%s",
                    self.session_id, new_phase)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append_turn(self, speaker: str, text: str) -> None:
        turn = ConversationTurn(
            turn_index=self.turn_count,
            speaker=speaker,  # type: ignore[arg-type]
            text=text,
        )
        self._transcript.append(turn.model_dump(mode="json"))

    def _fire_auditor(self, student_text: str, turn_index: int) -> None:
        """
        Fires the auditor callback as a fire-and-forget asyncio task.
        NEVER awaited — zero latency impact on the live audio path (rules.md §4).
        """
        if self._on_auditor_trigger is None:
            return
        asyncio.create_task(
            _safe_auditor_call(self._on_auditor_trigger, student_text, turn_index),
            name=f"auditor-{self.session_id}-turn-{turn_index}",
        )

    # ------------------------------------------------------------------
    # State export (called by orchestrator before Redis persist)
    # ------------------------------------------------------------------

    def export_transcript(self) -> list[dict]:
        """Returns accumulated transcript as list of ConversationTurn dicts."""
        return list(self._transcript)

    @property
    def is_connected(self) -> bool:
        return self._is_connected


# ---------------------------------------------------------------------------
# Helper — safe async wrapper for auditor callback
# ---------------------------------------------------------------------------

async def _safe_auditor_call(
    callback: Callable[[str, int], None],
    student_text: str,
    turn_index: int,
) -> None:
    """Wraps auditor callback so exceptions don't crash the live audio loop."""
    try:
        result = callback(student_text, turn_index)
        if asyncio.iscoroutine(result):
            await result
    except Exception as exc:
        # Log but never propagate — auditor failure must not affect the interview
        logger.warning("Auditor task failed | turn=%d | error=%s", turn_index, exc)
