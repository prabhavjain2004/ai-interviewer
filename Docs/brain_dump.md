# Brain Dump — Senior Agentic AI Engineer Notes

## Project: AI Technical Interviewer & Mentor (Ribbon.ai Killer)

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
| .env.example | DONE | Env var template — built 2026-03-18 |

---

## ARCHITECTURE DECISIONS (LOCKED)

### The Hybrid Model Split
- Gemini 1.5 Flash Live = interview layer ONLY (sub-500ms, native multimodal, WebSocket)
- Gemini 1.5 Pro = resume parsing + post-interview coaching ONLY (quality over speed)
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
