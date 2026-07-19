"""Daily AI Challenge endpoints (spec §3.8)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Challenge, User
from ..responses import error, ok
from ..skills.challenges import generate_challenge
from ..skills.gamification import record_activity

router = APIRouter(prefix="/challenges", tags=["challenges"])

XP_REWARD = 15


def _dict(c: Challenge) -> dict:
    return {
        "id": c.id,
        "day": c.day.isoformat(),
        "title": c.title,
        "description": c.description,
        "completed": c.completed,
    }


@router.get("/today")
async def today(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Return today's challenge, generating and persisting it once per day."""
    day = datetime.now(timezone.utc).date()
    existing = await session.execute(
        select(Challenge).where(Challenge.user_id == user.id, Challenge.day == day)
    )
    challenge = existing.scalar_one_or_none()
    if challenge is None:
        gen = await generate_challenge(user.goal or "grow my career", day.toordinal())
        challenge = Challenge(
            user_id=user.id, day=day, title=gen["title"], description=gen.get("description")
        )
        session.add(challenge)
        await session.commit()
    return ok(data=_dict(challenge))


@router.post("/{challenge_id}/complete")
async def complete(
    challenge_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Complete today's challenge → award XP + streak + achievements (once)."""
    challenge = await session.get(Challenge, challenge_id)
    if challenge is None or challenge.user_id != user.id:
        return error("Challenge not found.", status_code=404, code="not_found")

    earned = []
    if not challenge.completed:
        challenge.completed = True
        challenge.completed_at = datetime.now(timezone.utc)
        new_achievements = await record_activity(session, user, xp=XP_REWARD)
        earned = [a.title for a in new_achievements]

    await session.commit()
    return ok(
        data={
            **_dict(challenge),
            "xp": user.xp,
            "level": user.level,
            "streak": user.streak,
            "new_achievements": earned,
        },
        message="Challenge completed",
    )


@router.get("/history")
async def history(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    rows = await session.execute(
        select(Challenge)
        .where(Challenge.user_id == user.id)
        .order_by(Challenge.day.desc())
        .limit(30)
    )
    return ok(data=[_dict(c) for c in rows.scalars().all()])
