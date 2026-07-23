"""Subscription / billing (spec extension): plans, current status, and upgrades.

Payment is stubbed like the rest of the app — subscribing sets the tier
immediately. Wiring real Stripe checkout is a clean follow-up.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user, user_is_admin
from ..models import User
from ..plans import LIMITS, PLANS, ai_used_today, limit_for, tier_of
from ..responses import ok
from ..schemas import SubscribeRequest

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans")
async def list_plans(user: User = Depends(get_current_user)) -> object:
    """The three plans + which one the user is on."""
    return ok(data={"plans": PLANS, "current": tier_of(user)})


@router.get("/me")
async def my_subscription(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Current tier, effective limits, and today's AI usage."""
    tier = tier_of(user)
    ai_limit = limit_for(user, "ai_daily")
    return ok(
        data={
            "tier": tier,
            "is_admin": user_is_admin(user),
            "limits": LIMITS.get(tier, LIMITS["free"]),
            "ai_used_today": await ai_used_today(session, user),
            "ai_daily_limit": ai_limit,
        }
    )


@router.post("/subscribe")
async def subscribe(
    payload: SubscribeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Change plan (payment stubbed — applies immediately)."""
    user.tier = payload.tier
    await session.commit()
    names = {"free": "Free", "pro": "Pro", "elite": "Elite"}
    msg = (
        "Your plan was cancelled — you're back on Free."
        if payload.tier == "free"
        else f"You're on {names[payload.tier]} now. Enjoy!"
    )
    return ok(data={"tier": payload.tier}, message=msg)
