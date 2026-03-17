"""
api/routes/resume.py
--------------------
POST /resume/upload — accepts resume file, saves to temp storage.
Returns the file path for use in POST /session/start.
File is deleted by core/parser.py after text extraction (rules.md §6).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/resume", tags=["resume"])

RESUME_DIR = Path("data/resumes")
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB


class ResumeUploadResponse(BaseModel):
    file_path: str
    filename: str
    size_bytes: int


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...)) -> ResumeUploadResponse:
    """
    Accepts a resume file upload and saves it to data/resumes/ with a UUID filename.
    Returns the file_path — pass this to POST /session/start.

    Supported formats: PDF, TXT, MD.
    Max size: 5MB.
    File is deleted by core/parser.py after parsing — not stored permanently.
    """
    # Validate extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {ALLOWED_EXTENSIONS}",
        )

    # Read content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {MAX_FILE_SIZE_BYTES // 1024 // 1024}MB",
        )

    # Save with UUID name to avoid collisions
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4()}{suffix}"
    dest = RESUME_DIR / unique_name
    dest.write_bytes(content)

    logger.info("Resume uploaded | size=%d bytes | saved_as=%s", len(content), unique_name)

    return ResumeUploadResponse(
        file_path=str(dest),
        filename=file.filename or unique_name,
        size_bytes=len(content),
    )
