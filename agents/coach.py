"""
agents/coach.py
---------------
Agent 3: The Coach — Mirror & Mentor report via Gemini 1.5 Pro.

Rules obeyed:
- Gemini Pro ONLY — never Flash (rules.md §1)
- Strictly separated from interviewer.py — no interview logic here (rules.md §4)
- Standalone async function — not a class method (rules.md §4)
- Every FeedbackItem MUST have all 4 fields: student_quote, resume_claim,
  diagnosis, elite_script (rules.md §5)
- Exactly 6 FeedbackItems — one per Wellfound category (hld.md §6)
- Elite Script: 15-30 sec, STAR, metric, industry terminology (hld.md §5)
- Runs as FastAPI BackgroundTask — never blocks session close (architecture.md §6)
- Result saved to Redis under session_id:report (architecture.md §7)
- No PII in logs (rules.md §6)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from google import genai
from google.genai import types as genai_types
from pydantic import ValidationError

from core.state import (
    CoachReport,
    FeedbackItem,
    InterviewState,
    MirrorResult,
)

logger = logging.getLogger(__name__)

PRO_MODEL = "models/gemini-2.5-pro"

# ---------------------------------------------------------------------------
# Wellfound categories — must match FeedbackItem.category Literal exactly
# ---------------------------------------------------------------------------

WELLFOUND_CATEGORIES = [
    "Technical Depth",
    "Communication Clarity",
    "Resume Consistency",
    "Problem-Solving Approach",
    "Ownership & Impact",
    "Cultural & Role Fit",
]


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_coach_prompt(state: InterviewState) -> str:
    resume_json = state.get("resume_json", {})
    transcript = state.get("transcript", [])
    auditor_notes = state.get("auditor_notes", [])

    # Format transcript for readability
    transcript_str = "\n".join(
        f"[{t.get('speaker', '?').upper()} | turn {t.get('turn_index', '?')}]: {t.get('text', '')}"
        for t in transcript
    )

    # Summarise auditor notes
    auditor_str = json.dumps(auditor_notes, indent=2)
    resume_str = json.dumps(resume_json, indent=2)

    return f"""You are an elite technical interview coach. Your job is to generate a structured
Mirror & Mentor coaching report for a university student who just completed a technical interview.

You have three inputs:
1. The student's resume (ground truth of what they CLAIM to have done).
2. The full interview transcript (what they ACTUALLY said).
3. Auditor notes (real-time flags: filler words, missing metrics, vague ownership).

Your output must be a JSON object with exactly this structure:
{{
  "session_id": "<session_id>",
  "overall_score": <float 1.0-10.0>,
  "summary": "<2-3 sentence overall coaching summary — encouraging but honest>",
  "feedback": [
    {{
      "category": "<one of the 6 Wellfound categories>",
      "score": <int 1-10>,
      "student_quote": "<exact words from transcript — most representative for this category>",
      "resume_claim": "<what the resume says they did — directly relevant to this category>",
      "diagnosis": "<specific named weakness — NOT generic. E.g. 'Missing quantifiable outcome on Redis caching claim' not 'answer was weak'>",
      "elite_script": "<15-30 second rewrite. MUST use STAR structure, industry terminology, and at least one metric>",
      "is_derived_metric": <true if the metric in elite_script was found verbatim in the resume power_facts, false if it is a suggested placeholder>,
      "mirror": {{
        "resume_claim": "<resume claim being compared>",
        "student_said": "<what student actually said>",
        "gap": "<specific gap between claim and verbal answer>",
        "consistency": "<strong | moderate | weak>"
      }}
    }}
  ]
}}

The 6 categories you MUST cover (one FeedbackItem each, in this order):
1. Technical Depth
2. Communication Clarity
3. Resume Consistency
4. Problem-Solving Approach
5. Ownership & Impact
6. Cultural & Role Fit

Elite Script requirements (non-negotiable):
- 50-100 words (15-30 seconds spoken)
- STAR structure: Situation → Task → Action → Result
- Must include at least one metric (use resume power_facts if available, otherwise suggest a placeholder like "[X]%")
- Must use industry-standard terminology for the student's tech stack
- Must sound natural — not robotic

Tone for summary and diagnosis: Encouraging but technically honest.
Think "senior engineer who wants you to succeed" — not a judge.

--- STUDENT RESUME ---
{resume_str}

--- INTERVIEW TRANSCRIPT ---
{transcript_str}

--- AUDITOR NOTES ---
{auditor_str}

--- SESSION ID ---
{state.get("session_id", "unknown")}

Now generate the coaching report JSON:"""


# ---------------------------------------------------------------------------
# Response schema for Gemini structured output
# ---------------------------------------------------------------------------

_MIRROR_SCHEMA = {
    "type": "object",
    "properties": {
        "resume_claim": {"type": "string"},
        "student_said": {"type": "string"},
        "gap": {"type": "string"},
        "consistency": {"type": "string", "enum": ["strong", "moderate", "weak"]},
    },
    "required": ["resume_claim", "student_said", "gap", "consistency"],
}

_FEEDBACK_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "score": {"type": "integer"},
        "student_quote": {"type": "string"},
        "resume_claim": {"type": "string"},
        "diagnosis": {"type": "string"},
        "elite_script": {"type": "string"},
        "is_derived_metric": {"type": "boolean"},
        "mirror": _MIRROR_SCHEMA,
    },
    "required": ["category", "score", "student_quote", "resume_claim",
                 "diagnosis", "elite_script", "is_derived_metric", "mirror"],
}

_COACH_REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "session_id": {"type": "string"},
        "overall_score": {"type": "number"},
        "summary": {"type": "string"},
        "feedback": {
            "type": "array",
            "items": _FEEDBACK_ITEM_SCHEMA,
            "minItems": 6,
            "maxItems": 6,
        },
    },
    "required": ["session_id", "overall_score", "summary", "feedback"],
}


# ---------------------------------------------------------------------------
# Core coach node
# ---------------------------------------------------------------------------

async def generate_coach_report(
    state: InterviewState,
    api_key: str,
) -> CoachReport:
    """
    Generates the Mirror & Mentor coaching report using Gemini 1.5 Pro.

    Called as a FastAPI BackgroundTask after interview status=finished.
    Single Pro call with structured output — guaranteed JSON schema.

    Returns:
        CoachReport — validated Pydantic model.

    Raises:
        ValueError: If Pro returns unparseable or incomplete output.
    """
    session_id = state.get("session_id", "unknown")
    logger.info("Coach report generation started | session=%s", session_id)

    client = genai.Client(api_key=api_key)
    prompt = _build_coach_prompt(state)

    response = await client.aio.models.generate_content(
        model=PRO_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_COACH_REPORT_SCHEMA,
            temperature=0.4,  # Some creativity for Elite Scripts, but structured
        ),
    )

    raw_json = response.text
    if not raw_json:
        raise ValueError(f"Gemini Pro returned empty coaching report | session={session_id}")

    try:
        data = json.loads(raw_json)
        feedback_items = [
            FeedbackItem(
                category=item["category"],
                score=item["score"],
                student_quote=item["student_quote"],
                resume_claim=item["resume_claim"],
                diagnosis=item["diagnosis"],
                elite_script=item["elite_script"],
                is_derived_metric=item.get("is_derived_metric", False),
                mirror=MirrorResult(**item["mirror"]),
            )
            for item in data["feedback"]
        ]

        report = CoachReport(
            session_id=session_id,
            generated_at=datetime.now(timezone.utc),
            overall_score=float(data["overall_score"]),
            feedback=feedback_items,
            summary=data["summary"],
        )

    except (json.JSONDecodeError, KeyError, ValidationError) as exc:
        raise ValueError(
            f"Coach report parsing failed | session={session_id} | error={exc}"
        ) from exc

    logger.info(
        "Coach report generated | session=%s | overall_score=%.1f | categories=%d",
        session_id,
        report.overall_score,
        len(report.feedback),
    )
    return report


# ---------------------------------------------------------------------------
# Background task wrapper
# Called by api/routes/session.py via FastAPI BackgroundTasks
# ---------------------------------------------------------------------------

async def run_coach_background(
    state: InterviewState,
    api_key: str,
    redis_client: "RedisClient",  # type: ignore[name-defined]  # imported at call site
) -> None:
    """
    Wrapper for running coach as a FastAPI BackgroundTask.
    Generates report and saves to Redis under session:{session_id}:report.
    Never raises — exceptions are caught and logged.
    Dedup guard: skips if report already exists (prevents double-trigger).
    """
    session_id = state.get("session_id", "unknown")
    try:
        # Dedup guard — if report already exists, skip
        existing = await redis_client.load_report(session_id)
        if existing:
            logger.info("Coach report already exists — skipping duplicate | session=%s", session_id)
            return
        report = await generate_coach_report(state, api_key)
        await redis_client.save_report(session_id, report.model_dump(mode="json"))
        logger.info("Coach report saved to Redis | key=%s", redis_client.report_key(session_id))
    except Exception as exc:
        logger.error(
            "Coach background task failed | session=%s | error=%s",
            session_id, exc,
        )
