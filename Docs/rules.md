# Operational Rules — AI Interviewer & Mentor Platform

## 1. Model Usage Rules (STRICT)

- **Flash for Talk, Pro for Feedback. No exceptions.**
  - Gemini 1.5 Flash Live: ONLY for the real-time interview conversation.
  - Gemini 1.5 Pro: ONLY for resume parsing (entity extraction) and post-interview coaching report.
  - Never use Pro during the live interview loop — it will break the sub-500ms latency target.
  - Never use Flash for the coaching report — it lacks the reasoning depth required.

---

## 2. Persona Rules (No "Judge" Persona)

- The AI is a Supportive Partner, not an evaluator or judge.
- Tone: Encouraging but technically firm. Think "senior engineer who wants you to succeed."
- Prohibited phrases: "That's wrong", "Incorrect", "You failed to mention."
- Required approach: Ask follow-up questions that guide the student toward the right answer.
  - BAD: "That answer was vague."
  - GOOD: "Interesting — can you walk me through the specific caching strategy you used there?"
- The Interviewer never breaks character during the live session.
- Warmth is mandatory in `warm_up` phase. Technical pressure increases gradually through phases.

---

## 3. Entity Grounding Rules (MANDATORY)

- Every question in `deep_dive` and `stress_test` phases MUST reference a specific entity from
  the student's `resume_json`.
- The Interviewer system_instruction must include the full `resume_json` at session start.
- If a resume entity is "Tapnex project with Nexgen FC integration," the question must name
  "Tapnex" or "Nexgen FC" — not a generic "tell me about a project you worked on."
- Generic questions are only permitted in `warm_up` phase (max 2 turns).

---

## 4. Code Architecture Rules

- **Strict Separation:** Interviewer logic (Agent 1) and Coaching logic (Agent 3) must NEVER
  be in the same file or class.
- **Modular Nodes:** LangGraph nodes are standalone async functions, not methods on a class.
- **State is the Contract:** All inter-agent communication happens through `InterviewState`.
  Agents do not call each other directly.
- **Auditor is Passive:** The Auditor node never modifies the conversation. It only appends
  to `auditor_notes` in state.
- **No Blocking in Live Loop:** The Auditor runs as a parallel async task. It must never
  await inside the Flash Live response path.

---

## 5. Feedback Rules (Mirror & Mentor)

Every feedback item in the Coach report MUST contain all four of:
1. `student_quote` — the exact words the student used (from transcript).
2. `resume_claim` — what the resume says they did (from resume_json).
3. `diagnosis` — specific, named weakness (not generic). E.g., "Missing quantifiable outcome"
   not "answer was weak."
4. `elite_script` — a 15–30 second rewrite using STAR structure, industry terminology,
   and at least one metric.

Feedback without all four fields is considered incomplete and must not be returned.

---

## 6. Storage & Privacy Rules

- No raw audio stored on server at any point.
- Session JSON (transcript + scores + report) stored in Redis with 24-hour TTL only.
- Resume files deleted from disk immediately after parsing into `resume_json`.
- No PII logged to application logs (mask student name, email in all log statements).

---

## 7. Code Standards

- Python 3.10+ (use `match` statements for phase routing where appropriate).
- Strict Pydantic v2 models for all state objects — no raw dicts passed between agents.
- Async throughout: `async def` for all FastAPI endpoints, LangGraph nodes, and SDK calls.
- Type hints on every function signature — no `Any` types without explicit justification.
- Environment variables via `pydantic-settings` (`BaseSettings`) — no hardcoded API keys.
- All WebSocket handlers must implement graceful disconnect and state cleanup.
