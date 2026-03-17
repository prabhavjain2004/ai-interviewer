"""
core/state.py
-------------
Single source of truth for all data contracts in the system.

Rules obeyed:
- Pydantic v2 BaseModel for all sub-objects (rules.md §7)
- InterviewState as TypedDict for LangGraph node compatibility (brain_dump)
- Annotated reducers on list fields so LangGraph can merge parallel node outputs
- status: Literal["warm_up","deep_dive","stress_test","finished"] (hld.md §7)
- FeedbackItem enforces all 4 mandatory fields (rules.md §5)
- CoachReport has exactly 6 WellfoundCategory items (hld.md §6)
- No raw dicts passed between agents — always use these models (rules.md §7)
"""

from __future__ import annotations

import operator
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Resume Layer
# ---------------------------------------------------------------------------

class ProjectEntity(BaseModel):
    name: str
    tech_used: list[str] = Field(default_factory=list)
    outcome: str = ""


class RoleEntity(BaseModel):
    title: str
    company: str
    duration: str = ""


class ResumeProfile(BaseModel):
    """
    Output of core/parser.py — Gemini Pro entity extraction.
    Injected into InterviewState at session start.
    """
    raw_text: str = Field(description="Full resume text — used for ChromaDB embedding")
    projects: list[ProjectEntity] = Field(default_factory=list)
    roles: list[RoleEntity] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    career_goals: str = ""
    power_facts: list[str] = Field(
        default_factory=list,
        description="Quantifiable achievements e.g. 'reduced latency by 40%'"
    )


# ---------------------------------------------------------------------------
# Conversation Layer
# ---------------------------------------------------------------------------

class ConversationTurn(BaseModel):
    """One exchange in the live interview transcript."""
    turn_index: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    speaker: Literal["interviewer", "student"]
    text: str


# ---------------------------------------------------------------------------
# Auditor Layer  (Agent 2 — no LLM, pure heuristic)
# ---------------------------------------------------------------------------

class AuditorNote(BaseModel):
    """
    Per-turn scorecard filled by agents/auditor.py.
    Runs as asyncio.create_task() — never blocks the live loop.
    Emitted as real-time metadata over WebSocket for frontend heatmap.
    """
    turn_index: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metric_present: bool = False
    tech_stack_clarity: int = Field(default=1, ge=1, le=5)
    filler_word_count: int = 0
    red_flags: list[str] = Field(default_factory=list)
    resume_entity_referenced: str = ""
    # Real-time metadata fields — sent to frontend immediately after scoring
    hesitation_score: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="0.0=fluent, 1.0=very hesitant. Derived from filler_word_count / word_count"
    )
    word_count: int = 0


# ---------------------------------------------------------------------------
# Coaching Layer  (Agent 3 — Gemini Pro, post-interview only)
# ---------------------------------------------------------------------------

class MirrorResult(BaseModel):
    """
    Output of the Mirror Engine pass inside agents/coach.py.
    Compares resume claim vs what the student actually said.
    """
    resume_claim: str
    student_said: str
    gap: str
    consistency: Literal["strong", "moderate", "weak"]


class FeedbackItem(BaseModel):
    """
    One Wellfound category feedback block.
    All 4 fields are mandatory — rules.md §5.
    is_derived_metric: True = metric pulled from resume power_facts (verified).
                       False = metric is a suggested placeholder (student must fill in).
    """
    category: Literal[
        "Technical Depth",
        "Communication Clarity",
        "Resume Consistency",
        "Problem-Solving Approach",
        "Ownership & Impact",
        "Cultural & Role Fit",
    ]
    score: int = Field(ge=1, le=10)
    student_quote: str = Field(description="Exact words from transcript")
    resume_claim: str = Field(description="What the resume says they did")
    diagnosis: str = Field(description="Specific named weakness — not generic")
    elite_script: str = Field(
        description="15-30 sec STAR rewrite with metric and industry terminology"
    )
    mirror: MirrorResult
    is_derived_metric: bool = Field(
        default=False,
        description="True = metric verified from resume power_facts. False = suggested placeholder."
    )


class CoachReport(BaseModel):
    """
    Final output of agents/coach.py.
    Exactly 6 FeedbackItems — one per Wellfound category (hld.md §6).
    Stored in Redis under session_id:report with 24hr TTL.
    """
    session_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    overall_score: float = Field(ge=1.0, le=10.0)
    feedback: list[FeedbackItem] = Field(
        min_length=6,
        max_length=6,
        description="Exactly 6 items — one per Wellfound category"
    )
    summary: str = Field(description="2-3 sentence overall coaching summary")


# ---------------------------------------------------------------------------
# Top-Level Graph State  (LangGraph TypedDict)
# ---------------------------------------------------------------------------

from typing import TypedDict  # noqa: E402  (after pydantic imports for clarity)


class InterviewState(TypedDict, total=False):
    """
    LangGraph graph state — the single contract between all nodes.

    List fields use Annotated[list, operator.add] so LangGraph can safely
    merge outputs from parallel nodes (e.g. Auditor running alongside Interviewer).

    Rules:
    - Nodes receive this dict and return a PARTIAL dict (only changed keys).
    - Agents never call each other directly — only read/write this state.
    - Serialized to Redis as JSON after every node completion.
    """

    # Session metadata
    session_id: str
    created_at: str                          # ISO datetime string (JSON-serializable)

    # Resume context — set once at session init by core/parser.py
    resume_json: dict                        # ResumeProfile.model_dump()

    # Live transcript — grows with every turn
    # Annotated reducer: LangGraph merges lists from parallel nodes safely
    transcript: Annotated[list[dict], operator.add]   # ConversationTurn.model_dump()

    # Auditor notes — one AuditorNote per student turn
    auditor_notes: Annotated[list[dict], operator.add]  # AuditorNote.model_dump()

    # Phase machine — drives Interviewer question strategy
    status: Literal["warm_up", "deep_dive", "stress_test", "finished"]
    turn_count: int

    # Coach report — populated by agents/coach.py after status=finished
    coach_report: dict | None               # CoachReport.model_dump() or None
