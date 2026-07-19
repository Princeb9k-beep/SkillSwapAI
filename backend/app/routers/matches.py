"""AI Skill Matching endpoint (spec §2.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import User
from ..responses import ok
from ..skills.matching import find_matches

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("")
async def matches(
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """
    Return ranked complementary learning partners for the current user.
    Empty until the user has added some 'have'/'want' skills.
    """
    results = await find_matches(session, user, limit=limit)
    msg = (
        "Add skills you have and want to find matches."
        if not results
        else f"Found {len(results)} match(es)."
    )
    return ok(data=results, message=msg, meta={"count": len(results)})
