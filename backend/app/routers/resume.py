"""Resume builder endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_current_user
from ..models import User
from ..responses import ok
from ..schemas import ResumeRequest
from ..skills.resume import build_resume

from ..plans import require_feature

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/build", dependencies=[Depends(require_feature("career_tools"))])
async def build(
    payload: ResumeRequest, user: User = Depends(get_current_user)
) -> object:
    """Generate a tailored markdown resume."""
    markdown = await build_resume(
        payload.name, payload.target_role, payload.skills, payload.experience
    )
    return ok(data={"resume_markdown": markdown}, message="Resume generated")
