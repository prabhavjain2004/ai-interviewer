# Project Directory Structure

ai-interviewer-mentor/
├── .env                          # API keys (never committed)
├── .env.example                  # Template for env vars
├── main.py                       # FastAPI entry point
│
├── core/
│   ├── __init__.py
│   ├── state.py                  # Pydantic models + InterviewState TypedDict
│   ├── streaming_manager.py      # Gemini 1.5 Flash Live WebSocket manager
│   ├── orchestrator.py           # LangGraph graph definition + phase router
│   └── parser.py                 # Resume -> ResumeProfile (Gemini Pro entity extraction)
│
├── agents/
│   ├── __init__.py
│   ├── interviewer.py            # Agent 1: Flash Live conversation node
│   ├── auditor.py                # Agent 2: Parallel async scoring node
│   └── coach.py                  # Agent 3: Gemini Pro Mirror & Mentor report
│
├── prompts/
│   ├── interviewer_system.txt    # Flash Live system_instruction template
│   └── coach_system.txt          # Pro coaching report prompt template
│
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── session.py            # POST /session/start, DELETE /session/{id}
│   │   ├── resume.py             # POST /resume/upload
│   │   └── report.py             # GET /report/{session_id}
│   └── websocket.py              # WS /interview/{session_id} (audio stream)
│
├── services/
│   ├── __init__.py
│   ├── redis_client.py           # Redis connection + session state persistence
│   └── chroma_client.py          # ChromaDB per-session resume RAG
│
└── data/
    └── resumes/                  # Temp resume storage (deleted after parsing)
```

---

## Key File Responsibilities

| File | Owner Agent | Model Used |
|---|---|---|
| core/state.py | All agents | N/A (data contracts) |
| core/streaming_manager.py | Agent 1 | Gemini 1.5 Flash Live |
| core/orchestrator.py | LangGraph | N/A (routing logic) |
| core/parser.py | Session init | Gemini 1.5 Pro |
| agents/interviewer.py | Agent 1 | Gemini 1.5 Flash Live |
| agents/auditor.py | Agent 2 | Lightweight async (no LLM) |
| agents/coach.py | Agent 3 | Gemini 1.5 Pro |
| api/websocket.py | Transport | N/A (WebSocket handler) |
| services/redis_client.py | All | N/A (persistence) |

---

## Build Order

1. core/state.py
2. core/streaming_manager.py
3. agents/auditor.py
4. agents/interviewer.py
5. core/orchestrator.py
6. core/parser.py
7. agents/coach.py
8. prompts/ (both files)
9. services/ (redis + chroma)
10. api/ (routes + websocket)
11. main.py
