"""Gamification endpoints: personal progress + leaderboard (spec §3.1)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Achievement, User
from ..plans import ai_token_allowance, get_wallet
from ..responses import error, ok
from ..schemas import AchievementOut, DailyGoalRequest, LeaderboardEntry
from ..skills.gamification import week_key, xp_for_level

router = APIRouter(tags=["progress"])

# Cost (in AI tokens) to buy one streak freeze.
FREEZE_COST = 20

# League divisions by level.
LEAGUES = [
    (1, "Bronze"),
    (5, "Silver"),
    (10, "Gold"),
    (20, "Platinum"),
    (35, "Diamond"),
]


def _division(level: int) -> tuple[int, str]:
    """Return (min_level, name) for the user's league tier."""
    chosen = LEAGUES[0]
    for min_level, name in LEAGUES:
        if level >= min_level:
            chosen = (min_level, name)
    return chosen


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

    # Today's goal progress (day counter resets lazily elsewhere; show 0 if stale).
    day_xp = user.day_xp if user.day_xp_on == date.today() else 0
    goal = user.daily_goal or 30

    return ok(
        data={
            "xp": user.xp,
            "level": user.level,
            "streak": user.streak,
            "streak_freezes": user.streak_freezes,
            "daily_goal": goal,
            "day_xp": day_xp,
            "daily_goal_met": day_xp >= goal,
            "daily_goal_pct": min(100, round(100 * day_xp / max(1, goal))),
            "xp_into_level": into_level,
            "xp_for_next_level": next_floor - current_floor,
            "level_progress_pct": round(100 * into_level / span),
            "achievements": [
                AchievementOut.model_validate(a).model_dump(mode="json")
                for a in achievements
            ],
        }
    )


@router.post("/progress/daily-goal")
async def set_daily_goal(
    payload: DailyGoalRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Set the user's daily XP goal."""
    user.daily_goal = payload.xp
    await session.commit()
    return ok(data={"daily_goal": user.daily_goal}, message="Daily goal updated")


@router.post("/progress/buy-freeze")
async def buy_freeze(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Buy one streak freeze with AI tokens (free for unlimited/Elite)."""
    wallet = await get_wallet(session, user)
    allowance = ai_token_allowance(user)

    if allowance is not None:  # not unlimited — must be able to afford it
        allowance_remaining = max(0, allowance - (wallet.allowance_used or 0))
        balance = allowance_remaining + (wallet.purchased or 0)
        if balance < FREEZE_COST:
            return error(
                f"You need {FREEZE_COST} AI tokens to buy a streak freeze.",
                status_code=402,
                code="insufficient_tokens",
            )
        # Spend from purchased first, then the monthly allowance.
        remaining = FREEZE_COST
        take = min(wallet.purchased or 0, remaining)
        wallet.purchased -= take
        remaining -= take
        if remaining:
            wallet.allowance_used = (wallet.allowance_used or 0) + remaining

    user.streak_freezes = (user.streak_freezes or 0) + 1
    await session.commit()
    return ok(
        data={"streak_freezes": user.streak_freezes},
        message="Streak freeze added — one missed day is now forgiven.",
    )


@router.get("/league")
async def league(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """This week's league standings for the user's division (by weekly XP)."""
    min_level, name = _division(user.level)
    # Bound the division to the next tier's floor.
    idx = [lvl for lvl, _ in LEAGUES].index(min_level)
    max_level = LEAGUES[idx + 1][0] if idx + 1 < len(LEAGUES) else 10_000
    wk = week_key()

    rows = (
        await session.execute(
            select(User)
            .where(User.level >= min_level, User.level < max_level)
            .order_by(User.week_xp.desc(), User.id.asc())
            .limit(limit)
        )
    ).scalars().all()
    entries = [
        {
            "rank": i + 1,
            "user_id": u.id,
            "name": u.name or f"Learner #{u.id}",
            "week_xp": u.week_xp if u.week_key == wk else 0,
            "level": u.level,
            "is_me": u.id == user.id,
        }
        for i, u in enumerate(rows)
    ]
    return ok(data={"division": name, "week": wk, "entries": entries})


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
