"""Gamification endpoints: personal progress + leaderboard (spec §3.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Achievement, User
from ..responses import ok
from ..schemas import AchievementOut, LeaderboardEntry
from ..skills.gamification import xp_for_level

router = APIRouter(tags=["progress"])


@router.get("/progress")
async def progress(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Return the current user's XP, level, streak, and achievements."""
    result = await session.execute(
        select(Achievement)
        .where(Achievement.user_id == user.id)
        .order_by(Achievement.earned_at.desc())
    )
    achievements = result.scalars().all()

    current_floor = xp_for_level(user.level)
    next_floor = xp_for_level(user.level + 1)
    span = max(1, next_floor - current_floor)
    into_level = user.xp - current_floor

    return ok(
        data={
            "xp": user.xp,
            "level": user.level,
            "streak": user.streak,
            "xp_into_level": into_level,
            "xp_for_next_level": next_floor - current_floor,
            "level_progress_pct": round(100 * into_level / span),
            "achievements": [
                AchievementOut.model_validate(a).model_dump(mode="json")
                for a in achievements
            ],
        }
    )


@router.get("/leaderboard")
async def leaderboard(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Top learners by XP."""
    result = await session.execute(
        select(User).order_by(User.xp.desc(), User.id.asc()).limit(limit)
    )
    users = result.scalars().all()
    entries = [
        LeaderboardEntry(
            rank=i + 1,
            user_id=u.id,
            name=u.name or f"Learner #{u.id}",
            xp=u.xp,
            level=u.level,
        ).model_dump()
        for i, u in enumerate(users)
    ]
    return ok(data=entries)
