"""Subscription tiers, feature gating, and usage limits.

Three tiers — free / pro / elite — gate access to most paid features. Gating is
enforced on the backend (not just hidden in the UI): `require_feature(...)` is a
dependency that 402s with an upgrade message, and `enforce_ai_quota` caps the
Free tier's daily AI actions. Admins (ADMIN_EMAILS) are treated as elite so they
can exercise everything.
"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_session
from .deps import get_current_user, user_is_admin
from .models import AiUsage, User

TIERS = ("free", "pro", "elite")
_RANK = {"free": 0, "pro": 1, "elite": 2}

# Feature -> the set of tiers that unlock it, with a human label + the minimum
# tier name (for upgrade messages).
FEATURES: dict[str, dict] = {
    "video_rooms": {"tiers": {"pro", "elite"}, "min": "Pro", "label": "video practice rooms"},
    "academy_full": {"tiers": {"pro", "elite"}, "min": "Pro", "label": "the full Skill Academy"},
    "career_tools": {"tiers": {"pro", "elite"}, "min": "Pro", "label": "the resume & interview tools"},
    "twin_chat": {"tiers": {"pro", "elite"}, "min": "Pro", "label": "AI Twin chat"},
    "twin_train": {"tiers": {"elite"}, "min": "Elite", "label": "training your own AI Twin"},
    "verification": {"tiers": {"elite"}, "min": "Elite", "label": "skill verification"},
}

# Quantity limits per tier (None = unlimited).
LIMITS: dict[str, dict] = {
    "free": {"matches": 5, "ai_daily": 3, "marketplace_discount": 0},
    "pro": {"matches": None, "ai_daily": None, "marketplace_discount": 0},
    "elite": {"matches": None, "ai_daily": None, "marketplace_discount": 20},
}

# The catalog shown on the Plans page.
PLANS: list[dict] = [
    {
        "tier": "free",
        "name": "Free",
        "price_cents": 0,
        "tagline": "Everything you need to start swapping skills.",
        "features": [
            "AI skill matching — up to 5 matches",
            "Messaging, community & meetups",
            "Daily lessons & challenges",
            "Progress, XP & achievements",
            "3 AI actions / day (Coach, Scanner, Translate)",
            "Skill Academy — free preview lessons",
        ],
    },
    {
        "tier": "pro",
        "name": "Pro",
        "price_cents": 1200,
        "popular": True,
        "tagline": "Unlock the full AI learning toolkit.",
        "features": [
            "Unlimited matching & ranking",
            "Unlimited AI Coach, Scanner & Translate",
            "Video practice rooms",
            "Full Skill Academy — all courses included",
            "Resume builder & interview practice",
            "Chat with any AI Twin",
        ],
    },
    {
        "tier": "elite",
        "name": "Elite",
        "price_cents": 2900,
        "tagline": "Go pro, get verified, and stand out.",
        "features": [
            "Train your own AI Twin",
            "Skill verification badge",
            "20% off Marketplace & bookings",
            "Company partnerships — priority access",
            "Early access to new features",
            "Priority support",
        ],
    },
]


def tier_of(user: User) -> str:
    """Effective tier — admins act as elite so they can test every feature."""
    if user_is_admin(user):
        return "elite"
    return user.tier if user.tier in TIERS else "free"


def has_feature(user: User, feature: str) -> bool:
    spec = FEATURES.get(feature)
    return bool(spec) and tier_of(user) in spec["tiers"]


def limit_for(user: User, key: str) -> int | None:
    return LIMITS.get(tier_of(user), LIMITS["free"]).get(key)


def require_feature(feature: str):
    """Dependency: allow only tiers that include `feature`, else 402 + upgrade msg."""

    async def dep(user: User = Depends(get_current_user)) -> User:
        if not has_feature(user, feature):
            spec = FEATURES[feature]
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Upgrade to {spec['min']} to use {spec['label']}.",
            )
        return user

    return dep


async def enforce_ai_quota(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Dependency for AI endpoints: consume one of the Free tier's daily actions,
    or 402 when the daily limit is reached. Paid tiers are unlimited."""
    limit = limit_for(user, "ai_daily")
    if limit is None:
        return user

    today = date.today()
    row = (
        await session.execute(
            select(AiUsage).where(AiUsage.user_id == user.id, AiUsage.day == today)
        )
    ).scalar_one_or_none()
    used = row.count if row else 0
    if used >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"You've used your {limit} free AI actions today. "
                "Upgrade to Pro for unlimited AI."
            ),
        )
    if row is None:
        session.add(AiUsage(user_id=user.id, day=today, count=1))
    else:
        row.count = used + 1
    await session.commit()
    return user


async def ai_used_today(session: AsyncSession, user: User) -> int:
    row = (
        await session.execute(
            select(AiUsage).where(AiUsage.user_id == user.id, AiUsage.day == date.today())
        )
    ).scalar_one_or_none()
    return row.count if row else 0
