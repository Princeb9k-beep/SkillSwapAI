"""Referral endpoints: fetch your invite code, share link, and stats."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_session
from ..deps import get_current_user
from ..models import User
from ..referrals import bonus_tokens, ensure_referral_code, referral_count
from ..responses import ok

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get("/me")
async def my_referrals(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    code = await ensure_referral_code(session, user)
    count = await referral_count(session, user)
    bonus = bonus_tokens()
    link = f"{get_settings().frontend_url.rstrip('/')}/?ref={code}"
    return ok(
        data={
            "code": code,
            "link": link,
            "referred_count": count,
            "bonus_tokens": bonus,
            "tokens_earned": count * bonus,
        }
    )
