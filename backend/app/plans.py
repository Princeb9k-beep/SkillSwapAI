"""Subscription tiers, feature gating, and AI-token usage.

Three tiers — free / pro / elite — gate access to most paid features. Gating is
enforced on the backend (not just hidden in the UI): `require_feature(...)` is a
dependency that 402s with an upgrade message, and `consume_ai_token` spends one
AI token per AI action (monthly per-tier allowance first, then purchased top-up
tokens). Admins (ADMIN_EMAILS) are treated as elite so they can exercise
everything.
"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import get_session
from .deps import get_current_user, user_is_admin
from .models import AiWallet, User

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
    "free": {"matches": 5, "marketplace_discount": 0},
    "pro": {"matches": None, "marketplace_discount": 0},
    "elite": {"matches": None, "marketplace_discount": 20},
}

# Buyable AI-token top-up packs (payment stubbed). id -> tokens + price.
TOKEN_PACKS: list[dict] = [
    {"id": "small", "name": "Starter", "tokens": 500, "price_cents": 500},
    {"id": "medium", "name": "Booster", "tokens": 1500, "price_cents": 1200},
    {"id": "large", "name": "Power", "tokens": 5000, "price_cents": 3500},
]

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
            "100 AI tokens / month (Coach, Scanner, Translate)",
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
            "2,000 AI tokens / month + buyable top-ups",
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
            "Unlimited AI tokens — never run out",
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


def ai_token_allowance(user: User) -> int | None:
    """Monthly AI-token allowance for a user's tier (None = unlimited/elite)."""
    tier = tier_of(user)
    if tier == "elite":
        return None
    settings = get_settings()
    return settings.pro_ai_tokens if tier == "pro" else settings.free_ai_tokens


def _current_period() -> str:
    d = date.today()
    return f"{d.year:04d}-{d.month:02d}"


async def get_wallet(session: AsyncSession, user: User) -> AiWallet:
    """Fetch (or create) the user's wallet, rolling the monthly allowance over
    when a new calendar month has started. Caller commits."""
    period = _current_period()
    wallet = (
        await session.execute(select(AiWallet).where(AiWallet.user_id == user.id))
    ).scalar_one_or_none()
    if wallet is None:
        wallet = AiWallet(user_id=user.id, period=period, allowance_used=0, purchased=0)
        session.add(wallet)
    elif wallet.period != period:
        wallet.period = period
        wallet.allowance_used = 0
    return wallet


async def ai_token_status(session: AsyncSession, user: User) -> dict:
    """Snapshot of the user's token wallet for the API/UI."""
    allowance = ai_token_allowance(user)
    wallet = await get_wallet(session, user)
    await session.commit()  # persist any month rollover
    if allowance is None:
        return {
            "unlimited": True,
            "allowance": None,
            "allowance_used": 0,
            "allowance_remaining": None,
            "purchased": wallet.purchased,
            "balance": None,
            "period": wallet.period,
        }
    allowance_remaining = max(0, allowance - wallet.allowance_used)
    return {
        "unlimited": False,
        "allowance": allowance,
        "allowance_used": wallet.allowance_used,
        "allowance_remaining": allowance_remaining,
        "purchased": wallet.purchased,
        "balance": allowance_remaining + wallet.purchased,
        "period": wallet.period,
    }


async def add_purchased_tokens(session: AsyncSession, user: User, tokens: int) -> AiWallet:
    """Credit purchased top-up tokens to the wallet (payment stubbed)."""
    wallet = await get_wallet(session, user)
    wallet.purchased += tokens
    await session.commit()
    return wallet


async def consume_ai_token(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Dependency for AI endpoints: spend one AI token — from the monthly
    allowance first, then purchased top-ups — or 402 when the wallet is empty.
    Elite is unlimited."""
    allowance = ai_token_allowance(user)
    wallet = await get_wallet(session, user)
    if allowance is None:  # elite: unlimited
        await session.commit()  # persist any rollover
        return user

    if wallet.allowance_used < allowance:
        wallet.allowance_used += 1
    elif wallet.purchased > 0:
        wallet.purchased -= 1
    else:
        await session.commit()  # persist any rollover before failing
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                "You're out of AI tokens. Buy a top-up or upgrade your plan "
                "for more monthly tokens."
            ),
        )
    await session.commit()
    return user
