"""
agents/auditor.py
-----------------
Agent 2: The Auditor — passive, real-time background scorer.

Rules obeyed:
- NO LLM calls — pure Python heuristics only (brain_dump, rules.md §4)
- Runs as asyncio.create_task() — never blocks the Flash Live response path (rules.md §4)
- Only appends to auditor_notes in state — never modifies conversation (rules.md §4)
- Strict Pydantic v2 output (rules.md §7)
- No PII in logs (rules.md §6)
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

from core.state import AuditorNote

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heuristic constants
# ---------------------------------------------------------------------------

FILLER_WORDS: list[str] = [
    "um", "uh", "like", "you know", "basically", "literally",
    "sort of", "kind of", "i mean", "right", "so yeah",
]

# Regex: matches numbers with common metric suffixes
METRIC_PATTERN = re.compile(
    r"\b\d+(\.\d+)?\s*(%|ms|s|x|k|m|gb|mb|kb|users?|requests?|calls?|times?|hours?|days?)\b",
    re.IGNORECASE,
)

# Ownership signals — "I" vs "we" analysis
OWNERSHIP_STRONG = re.compile(r"\bI\s+(built|designed|implemented|led|created|wrote|deployed|owned|architected)\b", re.IGNORECASE)
OWNERSHIP_WEAK = re.compile(r"\b(we|our team|the team)\s+(built|designed|implemented|led|created|wrote|deployed)\b", re.IGNORECASE)

# Red flag patterns
VAGUE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("vague ownership claim", re.compile(r"\b(helped|assisted|supported|involved in|part of)\b", re.IGNORECASE)),
    ("no quantifiable outcome", re.compile(r"\b(better|faster|improved|optimized|enhanced)\b(?!.*\d)", re.IGNORECASE)),
    ("passive voice ownership", re.compile(r"\b(it was|was done|was built|was implemented)\b", re.IGNORECASE)),
    ("filler-heavy response", re.compile(r"\b(stuff|things|something|whatever|etc)\b", re.IGNORECASE)),
]


# ---------------------------------------------------------------------------
# Core scoring functions
# ---------------------------------------------------------------------------

def _count_filler_words(text: str) -> int:
    text_lower = text.lower()
    return sum(text_lower.count(fw) for fw in FILLER_WORDS)


def _check_metric_present(text: str) -> bool:
    return bool(METRIC_PATTERN.search(text))


def _score_tech_clarity(text: str, resume_tech_stack: list[str]) -> int:
    """
    Scores 1-5 based on how many resume tech entities appear in the answer.
    1 = none mentioned, 5 = 4+ mentioned with context.
    """
    if not resume_tech_stack:
        return 1
    text_lower = text.lower()
    hits = sum(1 for tech in resume_tech_stack if tech.lower() in text_lower)
    match hits:
        case 0:
            return 1
        case 1:
            return 2
        case 2:
            return 3
        case 3:
            return 4
        case _:
            return 5


def _detect_red_flags(text: str) -> list[str]:
    flags: list[str] = []
    for label, pattern in VAGUE_PATTERNS:
        if pattern.search(text):
            flags.append(label)
    # Ownership check
    has_strong = bool(OWNERSHIP_STRONG.search(text))
    has_weak = bool(OWNERSHIP_WEAK.search(text))
    if has_weak and not has_strong:
        flags.append("team credit without personal ownership")
    return flags


def _find_resume_entity_referenced(text: str, resume_json: dict) -> str:
    """Returns the first resume entity (project/company/tech) found in the answer."""
    text_lower = text.lower()
    for project in resume_json.get("projects", []):
        if project.get("name", "").lower() in text_lower:
            return project["name"]
    for role in resume_json.get("roles", []):
        if role.get("company", "").lower() in text_lower:
            return role["company"]
    for tech in resume_json.get("tech_stack", []):
        if tech.lower() in text_lower:
            return tech
    return ""


# ---------------------------------------------------------------------------
# Public auditor node
# ---------------------------------------------------------------------------

async def audit_turn(
    student_text: str,
    turn_index: int,
    resume_json: dict,
) -> AuditorNote:
    """
    Scores a single student answer. Pure heuristics — no LLM.
    Called via asyncio.create_task() from streaming_manager._fire_auditor().
    Returns AuditorNote — caller appends to InterviewState.auditor_notes.

    Never raises — exceptions are caught and logged so the live loop is never affected.
    """
    try:
        tech_stack: list[str] = resume_json.get("tech_stack", [])

        note = AuditorNote(
            turn_index=turn_index,
            timestamp=datetime.now(timezone.utc),
            metric_present=_check_metric_present(student_text),
            tech_stack_clarity=_score_tech_clarity(student_text, tech_stack),
            filler_word_count=_count_filler_words(student_text),
            red_flags=_detect_red_flags(student_text),
            resume_entity_referenced=_find_resume_entity_referenced(student_text, resume_json),
        )

        logger.debug(
            "Auditor scored turn | turn=%d | metric=%s | clarity=%d | fillers=%d | flags=%s",
            turn_index,
            note.metric_present,
            note.tech_stack_clarity,
            note.filler_word_count,
            note.red_flags,
        )
        return note

    except Exception as exc:
        logger.warning("Auditor scoring failed | turn=%d | error=%s", turn_index, exc)
        # Return a minimal note so state stays consistent
        return AuditorNote(
            turn_index=turn_index,
            timestamp=datetime.now(timezone.utc),
            red_flags=["auditor_error"],
        )


def make_auditor_callback(
    resume_json: dict,
    auditor_notes_sink: list[dict],
) -> "AuditorCallback":
    """
    Factory that returns a callback compatible with LiveInterviewer._on_auditor_trigger.
    The callback appends the AuditorNote dict to auditor_notes_sink in-place.
    The orchestrator reads auditor_notes_sink and merges into InterviewState.

    Usage in orchestrator:
        notes_sink: list[dict] = []
        callback = make_auditor_callback(resume_json, notes_sink)
        live_interviewer = LiveInterviewer(..., on_auditor_trigger=callback)
    """
    async def _callback(student_text: str, turn_index: int) -> None:
        note = await audit_turn(student_text, turn_index, resume_json)
        auditor_notes_sink.append(note.model_dump(mode="json"))

    return _callback


# Type alias for clarity
AuditorCallback = "Callable[[str, int], Coroutine[None, None, None]]"
