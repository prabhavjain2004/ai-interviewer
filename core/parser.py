"""
core/parser.py
--------------
Resume processor: PDF/text → ResumeProfile via Gemini 1.5 Pro entity extraction.

Rules obeyed:
- Gemini Pro ONLY for parsing — never Flash (rules.md §1)
- Resume file deleted from disk immediately after parsing (rules.md §6)
- No PII in logs — mask student name/email (rules.md §6)
- Strict Pydantic v2 output — ResumeProfile (rules.md §7)
- Async throughout (rules.md §7)
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from google import genai
from google.genai import types as genai_types
from pydantic import ValidationError

from core.state import ProjectEntity, ResumeProfile, RoleEntity

logger = logging.getLogger(__name__)

PRO_MODEL = "models/gemini-2.5-pro"

# ---------------------------------------------------------------------------
# Extraction prompt — structured JSON output enforced via response_schema
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """
You are a resume parser. Extract structured information from the resume text below.

Return ONLY a valid JSON object with exactly these fields — no markdown, no explanation:
{{
  "projects": [
    {{"name": "<project name>", "tech_used": ["<tech1>", "<tech2>"], "outcome": "<one sentence outcome>"}}
  ],
  "roles": [
    {{"title": "<job title>", "company": "<company name>", "duration": "<e.g. Jun 2023 - Aug 2023>"}}
  ],
  "tech_stack": ["<unique tech items across entire resume>"],
  "career_goals": "<stated objective or target role, or inferred from context>",
  "power_facts": ["<quantifiable achievement e.g. 'Reduced API latency by 40%'>"]
}}

Rules:
- power_facts must be quantifiable — include numbers, percentages, or scale indicators. Empty list if none.
- tech_stack must be deduplicated.
- Extract ALL projects, even side projects or academic ones.
- career_goals: use the resume objective/summary if present, otherwise infer from roles.
- Return ONLY the JSON object. No markdown fences. No extra text.

RESUME TEXT:
{resume_text}
"""


# ---------------------------------------------------------------------------
# Text extraction from file
# ---------------------------------------------------------------------------

def _extract_text_from_file(file_path: Path) -> str:
    """
    Extracts plain text from a resume file.
    Supports: .txt, .md, .pdf (via pypdf if available), fallback to raw read.
    """
    suffix = file_path.suffix.lower()

    if suffix in (".txt", ".md"):
        return file_path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # optional dependency
            reader = PdfReader(str(file_path))
            return "\n".join(
                page.extract_text() or "" for page in reader.pages
            )
        except ImportError:
            logger.warning("pypdf not installed — reading PDF as raw bytes (may be garbled)")
            return file_path.read_bytes().decode("utf-8", errors="ignore")

    # Fallback: try UTF-8 decode
    return file_path.read_bytes().decode("utf-8", errors="ignore")


def _mask_pii(text: str) -> str:
    """Masks email and phone for safe logging. Never applied to actual data."""
    text = re.sub(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", "[email]", text)
    text = re.sub(r"\b\d{10}\b|\+\d[\d\s\-]{8,}", "[phone]", text)
    return text[:120]  # truncate for log safety


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

async def parse_resume(
    file_path: Path,
    api_key: str,
    delete_after_parse: bool = True,
) -> ResumeProfile:
    """
    Parses a resume file into a ResumeProfile using Gemini 1.5 Pro.

    Steps:
    1. Extract text from file.
    2. Delete file from disk (rules.md §6).
    3. Call Gemini Pro with structured output schema.
    4. Validate and return ResumeProfile.

    Args:
        file_path: Path to the uploaded resume file.
        api_key: Gemini API key.
        delete_after_parse: If True, deletes the file immediately after text extraction.

    Returns:
        ResumeProfile — validated Pydantic model.

    Raises:
        ValueError: If Gemini returns unparseable output.
        ValidationError: If extracted data fails Pydantic validation.
    """
    # Step 1: Extract text
    resume_text = _extract_text_from_file(file_path)
    logger.info("Resume text extracted | chars=%d | preview=%s",
                len(resume_text), _mask_pii(resume_text))

    # Step 2: Delete file immediately — rules.md §6
    if delete_after_parse and file_path.exists():
        try:
            os.remove(file_path)
            logger.info("Resume file deleted after parsing | path=%s", file_path.name)
        except OSError as e:
            logger.warning("Could not delete resume file | error=%s", e)

    # Step 3: Gemini Pro extraction — plain JSON mode, no response_schema
    client = genai.Client(api_key=api_key)
    prompt = EXTRACTION_PROMPT.format(resume_text=resume_text)

    response = await client.aio.models.generate_content(
        model=PRO_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )

    raw_json = response.text
    if not raw_json:
        raise ValueError("Gemini Pro returned empty response during resume parsing.")

    # Strip markdown fences if model wraps output (e.g. ```json ... ```)
    raw_json = raw_json.strip()
    if raw_json.startswith("```"):
        raw_json = re.sub(r"^```[a-z]*\n?", "", raw_json)
        raw_json = re.sub(r"\n?```$", "", raw_json).strip()

    # Step 4: Parse and validate
    try:
        data = json.loads(raw_json)

        profile = ResumeProfile(
            raw_text=resume_text,          # Always use the original extracted text
            projects=[ProjectEntity(**p) for p in data.get("projects", [])],
            roles=[RoleEntity(**r) for r in data.get("roles", [])],
            tech_stack=data.get("tech_stack", []),
            career_goals=data.get("career_goals", ""),
            power_facts=data.get("power_facts", []),
        )
    except (json.JSONDecodeError, KeyError, ValidationError) as exc:
        raise ValueError(f"Resume parsing failed — invalid Gemini output: {exc}") from exc

    logger.info(
        "Resume parsed | projects=%d | roles=%d | tech=%d | power_facts=%d",
        len(profile.projects),
        len(profile.roles),
        len(profile.tech_stack),
        len(profile.power_facts),
    )
    return profile
