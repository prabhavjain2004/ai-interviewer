# Brain Dump — Senior Agentic AI Engineer Notes

## Project: AI Technical Interviewer & Mentor (Ribbon.ai Killer)

## 2026-03-18 Lead AI Engineer Audit Snapshot

- Objective: Compare implementation against architecture.md, rules.md, structure.md, and hld.md.
- Scope: Read-only code audit (no code changes), plus maintain this single tracking file.
- Immediate priority gaps found:
	- LangGraph is compiled but not truly orchestrating runtime transitions on the hot path.
	- HLD/architecture says native VAD barge-in is enabled, but code currently runs manual turn signaling with VAD disabled.
	- Horizontal scaling is constrained by in-process session registry dependency for active websocket sessions.
	- State contract drifts from strict typed models at graph boundary (dict-heavy state payloads).
	- Persistence safety risk: Redis outage fallback path depends on fakeredis but dependency is not pinned in requirements.

---

---

## STATUS TRACKER

| Component | Status | Notes |
|---|---|---|
| Docs/architecture.md | DONE | Hybrid Live architecture — updated 2026-03-18 |
| Docs/hld.md | DONE | VAD, Mirror Engine, Elite Script, 6-category report — updated 2026-03-18 |
| Docs/rules.md | DONE | Flash/Pro split, no-judge persona, entity grounding — updated 2026-03-18 |
| Docs/structure.md | DONE | Full project tree with api/ and services/ layers — updated 2026-03-18 |
| core/state.py | DONE | Pydantic v2 + TypedDict — built 2026-03-18 |
| core/streaming_manager.py | DONE | Gemini Flash Live WebSocket manager — built 2026-03-18 |
| core/orchestrator.py | DONE | LangGraph graph + phase router + InterviewSession — built 2026-03-18 |
| core/parser.py | DONE | Gemini Pro entity extraction, file deleted after parse — built 2026-03-18 |
| agents/interviewer.py | DONE | Agent 1 node + phase resolver — built 2026-03-18 |
| agents/auditor.py | DONE | Agent 2 pure heuristic, no LLM — built 2026-03-18 |
| agents/coach.py | DONE | Mirror & Mentor, 6-category Wellfound, Elite Script — built 2026-03-18 |
| prompts/ | DONE | interviewer_system.txt + coach_system.txt — built 2026-03-18 |
| services/redis_client.py | DONE | Async Redis, session/report helpers, 24hr TTL — built 2026-03-18 |
| services/chroma_client.py | DONE | Per-session ChromaDB, embed + query + cleanup — built 2026-03-18 |
| api/deps.py | DONE | FastAPI dependency injectors — built 2026-03-18 |
| api/routes/ | DONE | session, resume, report endpoints — built 2026-03-18 |
| api/websocket.py | DONE | WS audio bridge, concurrent recv/send tasks — built 2026-03-18 |
| main.py | DONE | FastAPI lifespan, all routers mounted — built 2026-03-18 |
| requirements.txt | DONE | All dependencies — built 2026-03-18 |
| templates/index.html | DONE | Basic UI — upload, live interview, transcript, report — built 2026-03-18 |

---

## ARCHITECTURE DECISIONS (LOCKED)

### The Hybrid Model Split
- Gemini 2.5 Flash Native Audio = interview layer ONLY (sub-500ms, native multimodal, WebSocket)
- Gemini 2.5 Pro = resume parsing + post-interview coaching ONLY (quality over speed)
- This is a HARD rule from rules.md — never swap these

### State Design
- Top-level: `InterviewState` as LangGraph TypedDict (nodes receive/return dicts)
- Sub-objects: Pydantic v2 BaseModel (ResumeProfile, ConversationTurn, AuditorNote, FeedbackItem, CoachReport)
- State is serialized to Redis as JSON on every node completion
- 24-hour TTL on all session data — auto-expires, no manual cleanup needed

### Auditor Design
- Runs as asyncio.create_task() — completely parallel to Flash Live response
- Never awaited in the live loop — zero latency impact
- Appends AuditorNote to state.auditor_notes list
- No LLM call — pure heuristic scoring (regex for filler words, keyword matching for tech clarity)
- This keeps it fast and cheap

### Phase Machine
- warm_up (2-3 turns) → deep_dive (4-5 turns) → stress_test (2-3 turns) → finished
- Phase stored in InterviewState.status
- LangGraph conditional edges route based on turn count + status
- Phase drives Interviewer's question strategy via system_instruction injection

### Scalability (traffic-safe design)
- LangGraph graph compiled ONCE at app startup (not per request)
- All workers are stateless — state lives in Redis only
- Flash Live WebSocket: one connection per session, managed by streaming_manager.py
- Coach runs as FastAPI BackgroundTask — doesn't block session close
- ChromaDB: per-session namespace, cleaned up on TTL expiry

### VAD (Barge-In)
- Native to Gemini Live — no extra library needed
- Enabled in the LiveGenerationConfig when opening the session
- Student can interrupt AI mid-sentence naturally

---

## WHAT EACH FILE DOES (quick ref)

```
core/state.py              — All Pydantic models + InterviewState TypedDict
core/streaming_manager.py  — Opens Flash Live WS, injects resume, handles audio I/O
core/orchestrator.py       — LangGraph graph: nodes, edges, phase routing
core/parser.py             — PDF/text resume → ResumeProfile JSON via Gemini Pro
agents/interviewer.py      — Agent 1: question generation node (uses Flash Live)
agents/auditor.py          — Agent 2: parallel scoring, no LLM, appends to auditor_notes
agents/coach.py            — Agent 3: Mirror & Mentor report via Gemini Pro
prompts/interviewer_system.txt — Flash Live system_instruction template (resume injected at runtime)
prompts/coach_system.txt   — Pro coaching prompt template
services/redis_client.py   — get/set/delete session state in Redis
services/chroma_client.py  — embed resume chunks, query by session_id
api/websocket.py           — WS /interview/{session_id} — bridges browser audio to Flash Live
api/routes/session.py      — POST /session/start, DELETE /session/{id}
api/routes/resume.py       — POST /resume/upload
api/routes/report.py       — GET /report/{session_id}
main.py                    — FastAPI app, mounts routes, compiles LangGraph graph
```

---

## DECISIONS LOG

### 2026-03-18 — Session 1
- Read original 4 docs, understood base architecture
- Decided on hybrid Pydantic + TypedDict state approach

### 2026-03-18 — Session 7 (current)
- BUG FIX: Double coach trigger — added dedup guard in `run_coach_background`: checks if report already exists in Redis before generating. Prevents two concurrent coach tasks from both running.
- BUG FIX: 10-15s response delay — root cause was native VAD + noise gate. Fan/background noise kept RMS above 0.015 threshold, causing Gemini's VAD to never detect silence. Fix: disabled VAD entirely (`disabled=True`) and switched to manual activity detection.
- NEW FEATURE: Manual turn signaling — frontend now has "Your Turn" button (sends `ACTIVITY_START`) and "Done Speaking" button (sends `TURN_COMPLETE` → `ACTIVITY_END`). User has explicit control over when their turn starts and ends. No more waiting for silence detection.
- API: Used `genai_types.ActivityStart()` and `genai_types.ActivityEnd()` in `LiveClientRealtimeInput` — confirmed correct SDK fields for manual VAD mode.
- Audio send: switched from `media_chunks=[Blob(...)]` to `audio=Blob(...)` (cleaner SDK field).
- UI: Added `btn-done` ("✅ Done Speaking") button, hidden until user presses "Your Turn". AI speaking state hides done button and resets speaking state.
- Report flow: confirmed `save_report`/`load_report` both use `session:{session_id}:report` key — no mismatch. Double coach was causing confusion in logs.
- BUG FIX 1: `sync_state_node` had `live_interviewer` as positional arg — LangGraph only passes `state`. Fixed by removing the arg from the node signature. `sync_to_state()` now does all data merging (transcript, auditor notes, turn_count) DIRECTLY before calling `graph.ainvoke()`. LangGraph is only used for phase routing logic now.
- BUG FIX 2: Flash Live session closed immediately with `1000 None`. Root cause: `connect().__aenter__()` was called but the context manager object was discarded — session was immediately garbage-collected/closed. Fixed by storing the CM as `self._live_cm` and calling `__aenter__()` on it, then `__aexit__()` on close.
- Both files diagnostics-clean after fixes.

### 2026-03-18 — Session 5 (current)
- Refinement 1: Mid-session RAG — ChromaDB queried on every student turn in deep_dive/stress_test, context injected into Flash Live as non-blocking asyncio.create_task()
- Refinement 2: Real-time auditor metadata — ws_metadata_sink added to InterviewSession, drained in send_task and pushed as JSON frames; frontend heatmap renders hesitation score, tech clarity, metric badge per turn
- Refinement 3: is_derived_metric on FeedbackItem — Pro instructed to set true only when metric is verbatim from resume power_facts; frontend shows "Verified metric" vs "Suggested — fill in your number"
- Refinement 4: 60-second reconnect buffer — disconnect records timestamp, session stays alive, reconnect resumes without triggering Coach; cleanup task fires after window expires
- All 8 modified files pass diagnostics clean

### 2026-03-18 — Session 4 (current)
- Built agents/auditor.py: pure heuristic scoring, no LLM, asyncio.create_task safe
- Built agents/interviewer.py: LangGraph node + phase resolver (warm_up→deep_dive→stress_test→finished)
- Built core/orchestrator.py: graph compiled once, InterviewSession runtime container, session registry
- All 3 files pass diagnostics clean
- Next: core/parser.py → agents/coach.py → prompts/ → services/ → api/ → main.py

### 2026-03-18 — Session 3 (current)
- Built core/state.py: all Pydantic v2 models + InterviewState TypedDict with Annotated reducers
- Built core/streaming_manager.py: LiveInterviewer class, VAD enabled, Auditor fired as asyncio.create_task()
- Both files pass diagnostics clean
- Next: agents/auditor.py → agents/interviewer.py → core/orchestrator.py

### 2026-03-18 — Session 2
- Major architecture upgrade: replaced Deepgram+ElevenLabs with Gemini 1.5 Flash Live
- Added VAD barge-in feature (native to Gemini Live)
- Added Mirror Engine (resume_power_facts vs student_said comparison)
- Added Elite Script requirement (15-30 sec, STAR, metric, industry terminology)
- Added 6-category Wellfound report structure
- Added api/ layer (routes + websocket handler)
- Added services/ layer (Redis + ChromaDB)
- Locked Flash/Pro model split as hard rule
- Updated all 4 docs + brain_dump
- STATUS: Waiting for user "go" signal to start building core/state.py + core/streaming_manager.py

---

## THINGS TO REMEMBER WHEN BUILDING

### core/state.py
- InterviewState is TypedDict (not BaseModel) — LangGraph requirement
- All list fields use Annotated[list, operator.add] for LangGraph reducer pattern
- status field: Literal["warm_up", "deep_dive", "stress_test", "finished"]
- AuditorNote is per-turn (list grows with each turn)
- FeedbackItem has 4 mandatory fields: student_quote, resume_claim, diagnosis, elite_script
- CoachReport has 6 FeedbackItems (one per Wellfound category)

### core/streaming_manager.py
- Use google-genai SDK (not google-generativeai — different SDK)
- LiveGenerationConfig: enable VAD, set response_modalities=["AUDIO"]
- system_instruction must include full resume_json as formatted string
- Audio input: raw PCM bytes from browser mic via WebSocket
- Audio output: raw PCM bytes back to browser via WebSocket
- On each transcript event: fire auditor_node as asyncio.create_task() (non-blocking)
- Handle disconnect gracefully: close Live session, save state to Redis, cleanup

### agents/auditor.py
- NO LLM calls — keep it pure Python
- Filler word list: ["um", "uh", "like", "you know", "basically", "literally", "sort of"]
- tech_stack_clarity: count how many resume tech entities appear in the answer (1-5 scale)
- metric_present: regex for numbers + units (%, ms, x, users, etc.)
- red_flags: list of string labels, not scores

### agents/coach.py
- Input: full InterviewState (transcript + resume_json + auditor_notes)
- Single Gemini Pro call with structured output (response_schema = CoachReport)
- Use Pydantic model as response schema for guaranteed JSON structure
- Run as BackgroundTask — result saved to Redis under session_id + ":report"

---

## OPEN QUESTIONS (for user)
- None currently — docs are clear, waiting for go signal

---

## ENV VARS NEEDED (for .env.example)
```
GEMINI_API_KEY=
REDIS_URL=redis://localhost:6379
CHROMA_HOST=localhost
CHROMA_PORT=8000
SESSION_TTL_SECONDS=86400
MAX_TURNS_WARM_UP=3
MAX_TURNS_DEEP_DIVE=5
MAX_TURNS_STRESS_TEST=3
```
