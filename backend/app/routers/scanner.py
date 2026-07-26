"""AI Skill Scanner endpoint (spec §3.9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from ..deps import get_current_user
from ..models import User
from ..responses import error, ok
from ..schemas import ScanRequest
from ..skills.extract import UnsupportedFile, extract_text
from ..skills.scanner import analyze

from ..plans import consume_ai_token

router = APIRouter(prefix="/scanner", tags=["scanner"])


@router.post("/analyze", dependencies=[Depends(consume_ai_token)])
async def scan(
    payload: ScanRequest,
    user: User = Depends(get_current_user),
) -> object:
    """Extract strengths, missing skills, and next steps from pasted text."""
    result = await analyze(payload.text, user.goal)
    return ok(data=result, message="Analysis complete")


@router.post("/analyze-file", dependencies=[Depends(consume_ai_token)])
async def scan_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> object:
    """Analyze an uploaded resume/document (PDF or text/code file)."""
    try:
        text = extract_text(file.filename or "", await file.read())
    except UnsupportedFile as exc:
        return error(str(exc), status_code=400, code="bad_file")
    result = await analyze(text, user.goal)
    return ok(data={**result, "source": file.filename}, message="Analysis complete")
