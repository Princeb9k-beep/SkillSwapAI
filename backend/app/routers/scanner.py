"""AI Skill Scanner endpoint (spec §3.9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ..models import User
from ..responses import ok
from ..schemas import ScanRequest
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
