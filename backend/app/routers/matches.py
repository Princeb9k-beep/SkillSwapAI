"""AI Skill Matching endpoint (spec §2.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import User
from ..responses import error, ok
from ..schemas import MatchFeedback
from ..skills.matching import find_matches, record_signal

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

    # Free tier sees a capped number of matches.
    from ..plans import limit_for

    cap = limit_for(user, "matches")
    capped = cap is not None and len(results) > cap
    if capped:
        results = results[:cap]

    msg = (
        "Add skills you have and want to find matches."
        if not results
        else f"Found {len(results)} match(es)."
    )
    return ok(
        data=results,
        message=msg,
        meta={"count": len(results), "capped": capped, "match_cap": cap},
    )


@router.post("/{partner_id}/feedback")
async def match_feedback(
    partner_id: int,
    payload: MatchFeedback,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Record feedback on a match ('interested' or 'dismissed'). Dismissed
    partners are hidden; interest (mutual especially) boosts ranking."""
    if partner_id == user.id:
        return error("You can't rate yourself.", status_code=400, code="invalid")
    partner = await session.get(User, partner_id)
    if partner is None:
        return error("User not found.", status_code=404, code="not_found")
    await record_signal(session, user.id, partner_id, payload.signal)
    await session.commit()
    return ok(message="Thanks — we'll tune your matches.")
