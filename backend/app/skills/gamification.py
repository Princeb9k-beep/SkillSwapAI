"""
Gamification (spec §3.1 + roadmap #4): XP, levels, streaks, achievements.

Deterministic, DB-only — no AI. Callers mutate the User in-session and commit;
these helpers never commit so they compose inside an endpoint's transaction.

Leveling curve: each level costs `LEVEL_STEP` more XP than the last (100, 200,
300, …), i.e. level N is reached at 50*N*(N-1) total XP. This keeps early levels
quick and later ones meaningful.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Achievement, User

LEVEL_STEP = 100

# code -> (title, description, predicate(user) -> bool)
ACHIEVEMENT_RULES = {
    "first_steps": ("First Steps", "Earned your first XP.", lambda u: u.xp >= 1),
    "level_5": ("Rising Star", "Reached level 5.", lambda u: u.level >= 5),
    "streak_3": ("On a Roll", "Hit a 3-day streak.", lambda u: u.streak >= 3),
    "streak_7": ("Committed", "Hit a 7-day streak.", lambda u: u.streak >= 7),
    "xp_500": ("Grinder", "Banked 500 XP.", lambda u: u.xp >= 500),
}


def level_for_xp(xp: int) -> int:
    """Total XP to reach level N is 50*N*(N-1); invert that."""
    level = 1
    while 50 * (level + 1) * level <= xp:
        level += 1
    return level


def xp_for_level(level: int) -> int:
    return 50 * level * (level - 1)


def award_xp(user: User, amount: int) -> None:
    """Add XP and recompute level (no commit)."""
    user.xp = (user.xp or 0) + max(0, amount)
    user.level = level_for_xp(user.xp)


def touch_streak(user: User, today: date | None = None) -> None:
    """Update the daily streak based on last activity (no commit)."""
    today = today or date.today()
    last = user.last_active_on
    if last == today:
        return  # already counted today
    if last == today - timedelta(days=1):
        user.streak = (user.streak or 0) + 1
    else:
        user.streak = 1
    user.last_active_on = today


async def sync_achievements(session: AsyncSession, user: User) -> list[Achievement]:
    """Award any newly-earned achievements (no commit). Returns the new ones."""
    result = await session.execute(
        select(Achievement.code).where(Achievement.user_id == user.id)
    )
    have = {row[0] for row in result.all()}
    newly: list[Achievement] = []
    for code, (title, desc, predicate) in ACHIEVEMENT_RULES.items():
        if code not in have and predicate(user):
            ach = Achievement(user_id=user.id, code=code, title=title, description=desc)
            session.add(ach)
            newly.append(ach)
    return newly


async def record_activity(
    session: AsyncSession, user: User, xp: int
) -> list[Achievement]:
    """Convenience: award XP, bump streak, sync achievements (no commit)."""
    award_xp(user, xp)
    touch_streak(user)
    return await sync_achievements(session, user)
