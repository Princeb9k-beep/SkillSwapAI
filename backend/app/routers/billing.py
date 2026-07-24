"""Subscription / billing (spec extension): plans, current status, and upgrades.

Payment is stubbed like the rest of the app — subscribing sets the tier
immediately. Wiring real Stripe checkout is a clean follow-up.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status

from ..database import get_session
from ..deps import get_current_user, user_is_admin
from ..models import User
from ..plans import (
    LIMITS,
    PLANS,
    TOKEN_PACKS,
    add_purchased_tokens,
    ai_token_status,
    tier_of,
)
from ..responses import ok
from ..schemas import BuyTokensRequest, SubscribeRequest

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
    """Current tier, effective limits, and AI-token wallet."""
    tier = tier_of(user)
    return ok(
        data={
            "tier": tier,
            "is_admin": user_is_admin(user),
            "limits": LIMITS.get(tier, LIMITS["free"]),
            "tokens": await ai_token_status(session, user),
        }
    )


@router.get("/tokens")
async def my_tokens(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """The user's AI-token wallet plus the buyable top-up packs."""
    return ok(
        data={
            "wallet": await ai_token_status(session, user),
            "packs": TOKEN_PACKS,
        }
    )


@router.post("/tokens/buy")
async def buy_tokens(
    payload: BuyTokensRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Buy a top-up pack (payment stubbed — tokens are credited immediately)."""
    pack = next((p for p in TOKEN_PACKS if p["id"] == payload.pack), None)
    if pack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown token pack."
        )
    await add_purchased_tokens(session, user, pack["tokens"])
    return ok(
        data={"wallet": await ai_token_status(session, user)},
        message=f"Added {pack['tokens']:,} AI tokens. Happy learning!",
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
