# High Level Design (HLD)

## 1. Feature: Resume-Driven Entity Grounding

The system uses Gemini 1.5 Pro to perform "Entity Extraction" on the uploaded resume at session start.
Extracted entities become "Question Anchors" — the Interviewer MUST pivot questions to specific
entities found in the resume.

Examples:
- Resume contains "Tapnex" project → Interviewer drills into "Nexgen FC integration" specifics.
- Resume contains "Python, FastAPI" → Interviewer pivots to "Python async trade-offs, why FastAPI over Django."
- Resume contains "Led a team of 4" → Interviewer probes for metrics: "What was the delivery timeline? What broke?"

Entity types extracted:
- `projects[]` — project names, tech used, outcomes
- `roles[]` — job titles, companies, durations
- `tech_stack[]` — languages, frameworks, tools
- `career_goals` — stated objective or target role
- `power_facts[]` — quantifiable achievements (e.g., "reduced latency by 40%")

---

## 2. Feature: Real-Time Barge-In (VAD)

- Voice Activity Detection (VAD) is enabled natively via Gemini Live.
- Students can interrupt the AI mid-sentence naturally — no "press to talk" UX.
- When barge-in is detected, the AI stops speaking and listens immediately.
- This mirrors a real human interview dynamic and reduces the "scripted bot" feel.
- Implementation: handled at the WebSocket audio stream level in `core/streaming_manager.py`.

---

## 3. Feature: Background Auditing (Real-Time)

The Auditor node runs as a parallel async task on every transcript event. It does NOT wait for the
Interviewer to finish responding. It fills the `AuditorNote` scorecard per turn:

```json
{
  "turn_index": 3,
  "timestamp": "2026-03-18T10:23:11Z",
  "metric_present": false,
  "tech_stack_clarity": 2,
  "filler_word_count": 7,
  "red_flags": ["vague ownership claim", "no quantifiable outcome"],
  "resume_entity_referenced": "Tapnex project"
}
```

Accumulated `auditor_notes` list in state feeds directly into the Coach agent at interview end.

---

## 4. Feature: The Mirror Engine

The Coach agent (Gemini 1.5 Pro) performs a "Mirror" pass first:
- Takes each student answer from the transcript.
- Compares it against the `resume_power_facts` (what the resume CLAIMS they did).
- Identifies gaps: things the resume claims but the student couldn't articulate verbally.
- Flags inconsistencies: resume says "led the project" but student said "I helped with..."

Mirror output per answer:
```json
{
  "resume_claim": "Reduced API response time by 40% using caching",
  "student_said": "I worked on making the API faster, used some Redis stuff",
  "gap": "Student could not articulate the specific technique or the metric",
  "consistency": "weak"
}
```

---

## 5. Feature: The Elite Script Engine

After the Mirror pass, the Coach generates an "Elite Script" for every weak or inconsistent answer.
This is the "Mentor" half of Mirror & Mentor.

Requirements for every Elite Script:
- Length: 15–30 seconds when spoken aloud (~50–100 words).
- Must use Industry Standard Terminology relevant to the tech stack.
- Must include a Quantifiable Metric (derived from resume or suggested as a placeholder).
- Must follow STAR structure (Situation, Task, Action, Result).
- Must sound natural — not robotic or over-formal.

Example:
```
Student said: "I worked on making the API faster, used some Redis stuff."

Elite Script:
"In my Tapnex project, our API response times were averaging 800ms under load, which was
causing drop-offs in the checkout flow. I diagnosed the bottleneck as repeated DB hits on
product catalog queries. I implemented a Redis caching layer with a 5-minute TTL on those
endpoints, which brought average response time down to under 120ms — a 40% improvement.
That directly improved our conversion rate in testing."
```

---

## 6. Feature: The 6-Category Wellfound Report

The Coach agent outputs a structured report with exactly 6 categories (mirroring Wellfound's
interview evaluation framework):

| # | Category | What it measures |
|---|---|---|
| 1 | Technical Depth | Accuracy and specificity of technical answers |
| 2 | Communication Clarity | Structure, conciseness, absence of filler words |
| 3 | Resume Consistency | Alignment between resume claims and verbal answers |
| 4 | Problem-Solving Approach | STAR structure, logical reasoning |
| 5 | Ownership & Impact | Use of "I" vs "we", quantifiable outcomes |
| 6 | Cultural & Role Fit | Alignment with stated career goals |

Each category includes:
- Score: 1–10
- Evidence: direct quote from transcript
- Diagnosis: specific weakness identified
- Elite Script: the rewritten version (15–30 sec)

---

## 7. Interview Phase Machine

LangGraph manages phase transitions via conditional edges:

```
warm_up (2-3 questions, rapport building)
    |
    v (after 2 turns)
deep_dive (4-5 questions, resume entity drilling)
    |
    v (after 4 turns)
stress_test (2-3 questions, edge cases, trade-offs, failure scenarios)
    |
    v (on completion signal or max turns)
finished (triggers Coach agent)
```

Phase is stored in `InterviewState.status` and drives the Interviewer's question strategy.
