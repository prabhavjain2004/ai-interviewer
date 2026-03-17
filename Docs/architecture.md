# System Architecture: AI Mentor Interviewer (Hybrid Live)

## 1. Overview
A hybrid multi-agent system that replaces the slow, scripted Ribbon.ai experience with a sub-500ms
Gemini Live interaction. The system conducts real-time voice interviews grounded in the student's
resume and delivers elite "Active Coaching" (Mirror & Mentor) post-interview.

---

## 2. The Three-Layer Architecture

### Layer 1 — Live Layer (Speed)
- **Model:** Gemini 1.5 Flash Live (Native Multimodal)
- **Protocol:** WebSocket (bidirectional audio stream)
- **Role:** Handles the real-time voice interview. Zero-latency voice-to-voice.
- **VAD:** Voice Activity Detection enabled — supports natural barge-in by the student.
- **Resume Injection:** Student's parsed resume JSON is injected as `system_instruction` at session start.

### Layer 2 — Logic Layer (Orchestration)
- **Framework:** LangGraph (stateful graph orchestration)
- **Role:** Manages the Interview State machine. Tracks resume context, live transcript, auditor notes,
  and interview phase transitions.
- **Auditor Node:** Runs as a parallel async branch on every transcript event. Does NOT block the
  Flash Live response. Flags technical red flags in real time.
- **State Persistence:** Session state serialized to Redis with 24-hour TTL. Stateless workers —
  safe for horizontal scaling.

### Layer 3 — Coaching Layer (Quality)
- **Model:** Gemini 1.5 Pro (long context, elite reasoning)
- **Role:** Post-interview only. Processes full transcript + resume_json to generate the
  Mirror & Mentor report. Does not need to be fast — needs to be elite.
- **Output:** Structured JSON with 6 Wellfound feedback categories + Elite Script alternatives.

---

## 3. Agentic Workflow (The Trinity)

| Agent | Model | Trigger | Responsibility |
|---|---|---|---|
| Interviewer (Agent 1) | Gemini 1.5 Flash Live | Session start / each turn | Real-time voice conversation, resume-grounded questions |
| Auditor (Agent 2) | Lightweight async | Every transcript event | Flags red flags, scores tech clarity, counts filler words |
| Coach (Agent 3) | Gemini 1.5 Pro | interview status = finished | Mirror & Mentor report, Elite Script generation |

---

## 4. Data Flow

```
Student Uploads Resume
        |
        v
core/parser.py  -->  ResumeProfile JSON  -->  ChromaDB (session namespace)
        |
        v
State Initialized (session_id, resume_json, status=warm_up)
        |
        v
Flash Live WebSocket Opens
  [Student Mic Audio]  -->  Flash Live  -->  [AI Voice Response]
        |                        |
        v                        v
  Transcript Event         Auditor Node (parallel, async)
  appended to State        logs to auditor_notes in State
        |
        v
  Phase Router (LangGraph conditional edge)
  warm_up -> deep_dive -> stress_test -> finished
        |
        v (on finished)
  Coach Agent (Gemini 1.5 Pro)
  Input: full transcript + resume_json
  Output: Mirror & Mentor JSON report
        |
        v
  Session JSON saved  -->  Redis (24hr TTL)
  No raw audio/video stored on server
```

---

## 5. Tech Stack

| Concern | Technology |
|---|---|
| Framework | LangGraph (stateful orchestration) |
| Live Interview Brain | Gemini 1.5 Flash Live (Native Multimodal) |
| Coaching Brain | Gemini 1.5 Pro |
| Voice Protocol | WebSocket (native audio stream) |
| VAD | Built-in Gemini Live VAD |
| Resume Parsing | Gemini 1.5 Pro (entity extraction) |
| Vector DB | ChromaDB (per-session resume RAG) |
| Backend | FastAPI (async) |
| State Persistence | Redis (24hr TTL, session_id keyed) |
| SDK | google-genai (Python) |

---

## 6. Scalability Design

- LangGraph graph compiled ONCE at startup, reused per session (never re-compiled per request).
- All state is external (Redis) — no in-memory session state. Workers are fully stateless.
- Flash Live WebSocket connections are per-session, managed by `core/streaming_manager.py`.
- Async throughout — FastAPI + async LangGraph nodes + async Gemini SDK calls.
- ChromaDB collections namespaced by session_id, cleaned up on TTL expiry.
- Coach agent runs as a background task (FastAPI `BackgroundTasks`) — does not block the
  session close response.

---

## 7. Storage Policy

- Session JSON (transcript + scores + report): Redis, 24-hour TTL, auto-expire.
- Resume files: Temp disk storage during session only, deleted on session close.
- No raw audio or video stored on server at any point.
