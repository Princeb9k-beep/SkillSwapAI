"""Referral / invite helpers.

Each user gets a short shareable code (assigned lazily). When a new account signs
up with someone's code, BOTH parties get bonus AI tokens credited to their wallet.
"""

from __future__ import annotations

import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import User

# Unambiguous alphabet (no 0/O/1/I) for codes that are easy to read/share.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_code(length: int = 8) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


async def ensure_referral_code(session: AsyncSession, user: User) -> str:
    """Return the user's referral code, generating a unique one on first use."""
    if user.referral_code:
        return user.referral_code
    for _ in range(10):
        code = _generate_code()
        exists = (
            await session.execute(select(User.id).where(User.referral_code == code))
        ).first()
        if not exists:
            user.referral_code = code
            await session.commit()
            return code
    # Extremely unlikely; fall back to a longer code.
    user.referral_code = _generate_code(12)
    await session.commit()
    return user.referral_code


async def referral_count(session: AsyncSession, user: User) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(User).where(User.referred_by_id == user.id)
        )
    ).scalar_one()


async def find_referrer(session: AsyncSession, code: str) -> User | None:
    normalized = code.strip().upper()
    if not normalized:
        return None
    return (
        await session.execute(select(User).where(User.referral_code == normalized))
    ).scalar_one_or_none()


def bonus_tokens() -> int:
    return get_settings().referral_bonus_tokens
