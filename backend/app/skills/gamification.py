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


def week_key(day: date | None = None) -> str:
    """ISO year+week identifier, e.g. '2026-30'."""
    d = day or date.today()
    y, w, _ = d.isocalendar()
    return f"{y}-{w:02d}"


def award_xp(user: User, amount: int, today: date | None = None) -> None:
    """Add XP, recompute level, and roll the daily + weekly counters (no commit)."""
    amount = max(0, amount)
    today = today or date.today()
    user.xp = (user.xp or 0) + amount
    user.level = level_for_xp(user.xp)

    # Daily counter (for the daily goal), reset when the day changes.
    if getattr(user, "day_xp_on", None) != today:
        user.day_xp = 0
        user.day_xp_on = today
    user.day_xp = (user.day_xp or 0) + amount

    # Weekly counter (for leagues), reset when the ISO week changes.
    wk = week_key(today)
    if getattr(user, "week_key", None) != wk:
        user.week_xp = 0
        user.week_key = wk
    user.week_xp = (user.week_xp or 0) + amount


def touch_streak(user: User, today: date | None = None) -> None:
    """Update the daily streak based on last activity (no commit). A single
    missed day is forgiven if the user has a streak freeze to spend."""
    today = today or date.today()
    last = user.last_active_on
    if last == today:
        return  # already counted today
    if last == today - timedelta(days=1):
        user.streak = (user.streak or 0) + 1
    elif last == today - timedelta(days=2) and (user.streak_freezes or 0) > 0:
        # Missed exactly one day — spend a freeze to keep the streak alive.
        user.streak_freezes -= 1
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
    """Convenience: award XP, bump streak, sync achievements (no commit).

    Newly-earned achievements also queue an in-app notification when the user
    has achievement alerts enabled."""
    from .feed import record_activity as _feed  # local import avoids a cycle

    old_level = user.level or 1
    award_xp(user, xp)
    touch_streak(user)
    if (user.level or 1) > old_level:
        _feed(session, user.id, "level_up", f"reached level {user.level}")

    newly = await sync_achievements(session, user)
    if newly and getattr(user, "notify_achievements", True):
        # Local import avoids a circular import (skills package ↔ models).
        from .notifications import create_notification
        from ..mailer import send_event_email

        for ach in newly:
            _feed(session, user.id, "achievement", f"earned '{ach.title}'")
            title = f"Achievement unlocked: {ach.title}"
            create_notification(
                session,
                user.id,
                type="achievement",
                title=title,
                body=ach.description,
                link="/progress",
            )
            try:  # best-effort email (no-op if SMTP off / pref disabled)
                await send_event_email(user, "achievement", title, ach.description, "/progress")
            except Exception:
                pass
    return newly
