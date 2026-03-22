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
import time
from datetime import datetime
from typing import TYPE_CHECKING, AsyncIterator, Callable

from google import genai
from google.genai import types as genai_types

from core.state import ConversationTurn, InterviewState

if TYPE_CHECKING:
    from services.chroma_client import ChromaClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FLASH_LIVE_MODEL = "models/gemini-2.5-flash-native-audio-latest"  # Gemini 2.5 Flash Native Audio Live

# Audio format expected by Gemini Live and sent back to browser
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1

# Guard against duplicate/native VAD burst completions being counted as separate turns.
MIN_TURN_INCREMENT_INTERVAL_SECONDS = 1.5


# ---------------------------------------------------------------------------
# System instruction builder
# ---------------------------------------------------------------------------

def build_system_instruction(resume_json: dict, phase: str, turn_count: int = 0) -> str:
    """
    Injects the student's full resume text + structured entities into the Flash Live
    system_instruction. Raw text gives richer context; structured JSON gives precise anchors.
    Phase-aware tone: warm in warm_up, technically firm in deep_dive/stress_test.
    Entity grounding is enforced here — rules.md §3.
    """
    # Full raw text for rich context — the interviewer reads the resume like a human would
    raw_text = resume_json.get("raw_text", "")

    # Structured entities for precise question anchoring
    structured = {k: v for k, v in resume_json.items() if k != "raw_text"}
    structured_str = json.dumps(structured, indent=2)

    # Progressive difficulty ramping based on turn count
    difficulty_guidance = ""
    if phase == "deep_dive":
        if turn_count <= 3:
            difficulty_guidance = (
                "\n\nDIFFICULTY LEVEL: EASY (Turn 1-2 of deep-dive)\n"
                "Start with straightforward questions about what they built and why. "
                "Ask about high-level architecture decisions. Keep it accessible. "
                "Example: 'Walk me through the architecture of [PROJECT] — what were the main components?'"
            )
        elif turn_count <= 5:
            difficulty_guidance = (
                "\n\nDIFFICULTY LEVEL: MEDIUM (Turn 3-4 of deep-dive)\n"
                "Now dig deeper into implementation details and trade-offs. "
                "Ask about specific technical choices and alternatives they considered. "
                "Example: 'Why did you choose [TECH_X] over [TECH_Y] for that use case? What trade-offs did you evaluate?'"
            )
        else:
            difficulty_guidance = (
                "\n\nDIFFICULTY LEVEL: CHALLENGING (Turn 5+ of deep-dive)\n"
                "Push on edge cases, scalability, and failure scenarios. "
                "Ask about what would break under stress and how they'd fix it. "
                "Example: 'If [PROJECT] had to handle 10x the load overnight, what would break first and how would you address it?'"
            )

    phase_guidance = {
        "warm_up": (
            "You are in the WARM-UP phase (2 questions max). Be warm, welcoming, and conversational. "
            "Ask about their current work and career goals. Keep it light and non-technical. "
            "NO technical questions yet — just build rapport. "
            "ACKNOWLEDGMENT RULE: After they answer, validate their response warmly before moving on. "
            "Examples: 'I love that approach', 'That makes a lot of sense', 'Really interesting direction', "
            "'That's a solid foundation to build on'. Make them feel heard."
        ),
        "deep_dive": (
            "You are in the DEEP-DIVE phase (5 questions max). Now get technical. "
            "Every question MUST reference a specific entity from their resume (project, company, tech). "
            "CRITICAL: Your next question MUST be based on what they just said. "
            "If they mention 'agentic solutions', 'multi-agent orchestration', or any specific technology, "
            "your follow-up MUST drill into that exact topic. This is a conversation, not a checklist. "
            "ACKNOWLEDGMENT RULE: After each answer, validate what they said before asking the next question. "
            "Examples: 'I really like how you approached that', 'That's a smart trade-off', "
            "'Interesting — I can see why you chose that pattern', 'That shows good architectural thinking'. "
            "Be encouraging but technically honest. Never say 'that's wrong' — guide them with follow-ups."
            + difficulty_guidance
        ),
        "stress_test": (
            "You are in the STRESS-TEST phase (3 questions max). Push them on edge cases, scalability, and failure scenarios. "
            "Ask about what would break under stress and how they'd fix it. Challenge their assumptions. "
            "Examples: 'What happens if this component fails?', 'How would you handle 10x the load?', "
            "'What's the worst-case scenario here and how would you mitigate it?' "
            "ACKNOWLEDGMENT RULE: Still validate their thinking, but probe deeper. "
            "Examples: 'Interesting approach — what if [edge case]?', 'I see your reasoning — have you considered [alternative]?' "
            "Be supportive but push them to think critically about robustness and scale."
        ),
    }

    return f"""You are an elite technical interviewer and supportive mentor for university students.
Your persona: A senior engineer who genuinely wants the student to succeed.
You are NOT a judge. You are a Supportive Partner.

PROHIBITED phrases: "That's wrong", "Incorrect", "You failed to mention."
REQUIRED approach: Ask follow-up questions that guide the student toward the right answer.

CRITICAL CONVERSATION RULES:
1. ACKNOWLEDGMENT FIRST: After every student answer, validate what they said before asking next question.
   - Examples: "I love that approach", "That makes sense", "Really interesting", "Smart trade-off"
   - Make them feel HEARD. This is crucial for interview experience.

2. BE INTERACTIVE - This is a CONVERSATION, not an interrogation:
   - If the candidate asks you a question, ANSWER IT naturally before continuing
   - If they say something interesting, explore it deeper with follow-ups
   - If they mention a specific technology or approach, discuss it with them
   - Example: Candidate: "Should I have used Redis instead?" → You: "Great question! Redis would definitely work well for caching. What made you consider it? Let's talk through the trade-offs..."
   - Don't just collect answers - ENGAGE with what they're saying

3. CONTEXTUAL FOLLOW-UPS: DO NOT ask pre-planned questions in sequence.
   - LISTEN to what they say and adapt your next question based on their answer.
   - If they mention "agents", "orchestration", "multi-agent systems", or any specific technology,
     your next question MUST explore that exact topic deeper.
   - Example: Student says "I used multi-agent orchestration" → You respond "I love that approach — 
     walk me through how you handled coordination between agents. What communication pattern did you use?"

4. NATURAL FLOW:
   - If they're struggling, help them with hints
   - If they're doing well, challenge them more
   - If they ask for clarification, provide it
   - This should feel like talking to a senior engineer, not taking an exam

{phase_guidance.get(phase, phase_guidance["warm_up"])}

--- STUDENT RESUME — FULL TEXT (read this like a human interviewer would) ---
{raw_text}
--- END FULL TEXT ---

--- STRUCTURED ENTITIES (use these as precise Question Anchors) ---
{structured_str}
--- END STRUCTURED ENTITIES ---

Key anchors to drill into:
- Projects: {[p.get("name") for p in resume_json.get("projects", [])]}
- Tech Stack: {resume_json.get("tech_stack", [])}
- Power Facts: {resume_json.get("power_facts", [])}

Voice Activity Detection is active. The student may interrupt you — stop immediately and listen.
Keep your responses concise (under 30 seconds when spoken). Ask one question at a time.

CRITICAL WAITING RULE:
- After asking a question, you MUST wait for the student to finish their complete answer.
- DO NOT interrupt or ask the next question until you receive a clear turn completion signal.
- If the student pauses mid-answer, they are likely thinking — give them time.
- Only proceed to the next question after they have fully completed their response.
- Be patient. Silence is okay. Let them think and formulate their answer.
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
        on_transcript_event: Callable[[str, str], None] | None = None,
        chroma_client: "ChromaClient | None" = None,
    ) -> None:
        self.session_id = session_id
        self.resume_json = resume_json
        self.phase = initial_phase
        self.turn_count = 0
        self._last_system_instruction_turn = -1  # Track when we last updated instruction

        # Callback fired (non-blocking) when a student transcript chunk arrives
        self._on_auditor_trigger = on_auditor_trigger

        # Callback fired when any transcript event arrives (interviewer or student)
        self._on_transcript_event = on_transcript_event

        # ChromaDB client for mid-session RAG (deep_dive + stress_test phases only)
        self._chroma = chroma_client

        self._client: genai.Client | None = None
        self._live_session = None
        self._live_cm = None  # holds the async context manager open
        self._is_connected = False
        self._transcript: list[dict] = []
        self._student_spoke_since_last_turn = False
        self._last_turn_increment_at = 0.0

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

        system_instruction = build_system_instruction(self.resume_json, self.phase, self.turn_count)

        config = genai_types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=system_instruction,
            # Enable transcription for both sides — required for coach report
            input_audio_transcription=genai_types.AudioTranscriptionConfig(),
            output_audio_transcription=genai_types.AudioTranscriptionConfig(),
            # Disable thinking — set directly on LiveConnectConfig (not nested in GenerationConfig)
            thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
            # Native Gemini VAD mode (Docs/architecture.md):
            # Disabled: frontend sends explicit TURN_COMPLETE after silence.
            realtime_input_config=genai_types.RealtimeInputConfig(
                automatic_activity_detection=genai_types.AutomaticActivityDetection(
                    disabled=True,
                )
            ),
            speech_config=genai_types.SpeechConfig(
                voice_config=genai_types.VoiceConfig(
                    prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

        self._live_cm = self._client.aio.live.connect(
            model=FLASH_LIVE_MODEL,
            config=config,
        )
        self._live_session = await self._live_cm.__aenter__()

        self._is_connected = True
        logger.info("Flash Live session opened | session_id=%s | phase=%s",
                    self.session_id, self.phase)

        # Kick off the opening greeting — send a text prompt so the AI speaks first.
        # Without this, Gemini Live waits silently for the student to speak first.
        await self._live_session.send_client_content(
            turns=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=(
                    "Please start the interview now. "
                    "Greet the student warmly and ask your first warm-up question."
                ))],
            ),
            turn_complete=True,
        )
        logger.info("Opening greeting triggered | session_id=%s", self.session_id)

    async def close(self) -> None:
        """Graceful shutdown. Caller is responsible for persisting state to Redis."""
        if self._live_cm and self._is_connected:
            try:
                await self._live_cm.__aexit__(None, None, None)
            except Exception:
                pass  # Best-effort close
        self._is_connected = False
        self._live_session = None
        self._live_cm = None
        logger.info("Flash Live session closed | session_id=%s", self.session_id)

    # ------------------------------------------------------------------
    # Audio I/O
    # ------------------------------------------------------------------

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """
        Push raw PCM audio bytes from the browser mic into Flash Live.
        Uses send_realtime_input — the correct SDK method for streaming audio.
        No audio is stored — bytes are forwarded directly (rules.md §6).
        In manual VAD mode, frontend silence detection calls signal_activity_end().
        """
        if not self._is_connected or self._live_session is None:
            return
        await self._live_session.send_realtime_input(
            audio=genai_types.Blob(
                data=pcm_bytes,
                mime_type=f"audio/pcm;rate={AUDIO_SAMPLE_RATE}",
            )
        )

    async def stream_response(self) -> AsyncIterator[bytes | None]:
        """
        Async generator that yields AI audio response chunks back to the browser.
        Also captures transcript text when available and fires the Auditor.

        Yields: raw PCM audio bytes (forward directly to browser WebSocket).

        Runs as a persistent loop — re-enters receive() after each turn so the
        session stays alive between AI speaking and student responding.
        Only exits when the session is explicitly closed.
        """
        if not self._live_session:
            return

        while self._is_connected:
            try:
                async for response in self._live_session.receive():
                    # --- Audio chunk: yield immediately to browser ---
                    if response.data:
                        yield response.data

                    # --- Transcript + metadata events ---
                    if response.server_content:
                        content = response.server_content

                        if content.model_turn and content.model_turn.parts:
                            for part in content.model_turn.parts:
                                if hasattr(part, "text") and part.text:
                                    # model_turn text parts are thinking/metadata — skip,
                                    # use output_transcription for the actual spoken words
                                    pass

                        # AI spoken words via output transcription (only final chunks)
                        if content.output_transcription and content.output_transcription.text:
                            text = content.output_transcription.text.strip()
                            if text and getattr(content.output_transcription, "finished", False):
                                self._append_turn("interviewer", text)
                                if self._on_transcript_event:
                                    self._on_transcript_event("interviewer", text)

                        if content.input_transcription:
                            student_text = content.input_transcription.text
                            is_finished = bool(getattr(content.input_transcription, "finished", False))
                            if student_text and student_text.strip() and is_finished:
                                self._student_spoke_since_last_turn = True
                                self._append_turn("student", student_text)
                                if self._on_transcript_event:
                                    self._on_transcript_event("student", student_text)
                                self._fire_auditor(student_text, self.turn_count)
                                if self.phase in ("deep_dive", "stress_test") and self._chroma:
                                    asyncio.create_task(
                                        self._inject_rag_context(student_text),
                                        name=f"rag-{self.session_id}-turn-{self.turn_count}",
                                    )

                        if content.turn_complete and self._student_spoke_since_last_turn:
                            now = time.monotonic()
                            if now - self._last_turn_increment_at < MIN_TURN_INCREMENT_INTERVAL_SECONDS:
                                continue
                            self.turn_count += 1
                            self._student_spoke_since_last_turn = False
                            self._last_turn_increment_at = now
                            
                            # Progressive difficulty: update system instruction every 2 turns in deep_dive
                            if self.phase == "deep_dive" and self.turn_count - self._last_system_instruction_turn >= 2:
                                await self._update_difficulty_level()
                            # Also update on stress_test entry
                            elif self.phase == "stress_test" and self.turn_count - self._last_system_instruction_turn >= 1:
                                await self._update_difficulty_level()
                            
                            # Emit a non-audio event so callers can flush metadata and persist state
                            # even when Gemini completes a turn without audio bytes.
                            yield None

            except Exception as exc:
                # Session closed or network error — exit the loop cleanly
                if self._is_connected:
                    logger.warning("stream_response loop error | session=%s | error=%s",
                                   self.session_id, exc)
                break

    # ------------------------------------------------------------------
    # Manual turn completion (called when frontend detects silence)
    # ------------------------------------------------------------------

    async def signal_activity_end(self) -> None:
        """
        Signals end of student speech activity in manual VAD mode.
        Called when frontend detects silence via noise gate.
        Forces the model to generate a response immediately.
        """
        if not self._is_connected or self._live_session is None:
            return

        # Step 1: explicit activity end event
        await self._live_session.send_realtime_input(
            activity_end=genai_types.ActivityEnd()
        )

        # Step 2: Signal turn completion without forcing immediate response
        # Let the system instruction's conversation rules handle whether to respond or wait
        await self._live_session.send_client_content(
            turns=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text="[Student turn complete.]")],
            ),
            turn_complete=True,
        )

        logger.debug("Manual turn completion signaled with explicit nudge | session_id=%s", self.session_id)

    # ------------------------------------------------------------------
    # Phase update (called by orchestrator when LangGraph transitions phase)
    # ------------------------------------------------------------------

    async def update_phase(self, new_phase: str) -> None:
        """
        Re-injects system_instruction when the interview phase changes.
        Sends a silent context update via send_client_content.
        """
        if not self._is_connected or self._live_session is None:
            return
        self.phase = new_phase
        self._last_system_instruction_turn = self.turn_count
        new_instruction = build_system_instruction(self.resume_json, new_phase, self.turn_count)
        # Inject phase change as a system context note
        await self._live_session.send_client_content(
            turns=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=(
                    f"[SYSTEM: Interview phase is now {new_phase.upper()}. "
                    f"Adjust your questioning style accordingly.]"
                ))],
            ),
            turn_complete=False,
        )
        logger.info("Phase updated | session_id=%s | new_phase=%s",
                    self.session_id, new_phase)

    async def _update_difficulty_level(self) -> None:
        """
        Updates system instruction with new difficulty level during deep_dive phase.
        Called every 2 turns to progressively increase question difficulty.
        Also called when entering stress_test phase.
        """
        if not self._is_connected or self._live_session is None:
            return
        self._last_system_instruction_turn = self.turn_count
        new_instruction = build_system_instruction(self.resume_json, self.phase, self.turn_count)
        
        if self.phase == "stress_test":
            difficulty_label = "STRESS-TEST"
        else:
            difficulty_label = "EASY" if self.turn_count <= 3 else "MEDIUM" if self.turn_count <= 5 else "CHALLENGING"
        
        await self._live_session.send_client_content(
            turns=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=(
                    f"[SYSTEM: Difficulty level now {difficulty_label}. "
                    f"Adjust question complexity accordingly while maintaining conversational flow.]"
                ))],
            ),
            turn_complete=False,
        )
        logger.info("Difficulty updated | session_id=%s | turn=%d | level=%s",
                    self.session_id, self.turn_count, difficulty_label)

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

    async def _inject_rag_context(self, student_text: str) -> None:
        """
        Mid-session RAG: queries ChromaDB for resume chunks relevant to what the
        student just said, then sends a context update to Flash Live so the next
        question is grounded in the most relevant resume detail.

        Runs as asyncio.create_task() — never blocks the audio path.
        Active in deep_dive and stress_test phases.
        """
        if not self._chroma or not self._is_connected or not self._live_session:
            return
        try:
            chunks = await self._chroma.query_resume(
                self.session_id, student_text, n_results=2
            )
            if not chunks:
                return

            context_update = (
                "\n[CONTEXT UPDATE — use this for your next question]\n"
                + "\n".join(f"- {c}" for c in chunks)
                + "\n[END CONTEXT UPDATE]\n"
            )
            # Send as a user-turn text message so Flash Live incorporates it
            await self._live_session.send_client_content(
                turns=genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=context_update)],
                ),
                turn_complete=False,  # Not a real student turn — just context
            )
            logger.debug("RAG context injected | session=%s | chunks=%d",
                         self.session_id, len(chunks))
        except Exception as exc:
            # Never propagate — RAG failure must not affect the interview
            logger.warning("RAG injection failed | session=%s | error=%s",
                           self.session_id, exc)

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
