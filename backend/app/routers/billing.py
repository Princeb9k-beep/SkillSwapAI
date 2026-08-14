"""Subscription / billing (spec extension): plans, current status, and upgrades.

Payment is stubbed like the rest of the app — subscribing sets the tier
immediately. Wiring real Stripe checkout is a clean follow-up.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import stripe_billing
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
from ..responses import error, ok
from ..schemas import BuyTokensRequest, SubscribeRequest

logger = logging.getLogger("skillswap.billing")
router = APIRouter(prefix="/billing", tags=["billing"])

_TIER_NAMES = {"free": "Free", "pro": "Pro", "elite": "Elite"}


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
    """Buy a token top-up pack.

    With Stripe configured this returns a Checkout URL to redirect to (tokens are
    credited by the webhook after payment). Without Stripe, it credits instantly.
    """
    pack = next((p for p in TOKEN_PACKS if p["id"] == payload.pack), None)
    if pack is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unknown token pack."
        )
    if stripe_billing.stripe_enabled():
        try:
            url = await stripe_billing.create_pack_checkout(user, payload.pack)
        except Exception:
            logger.exception("Stripe pack checkout failed")
            return error("We couldn't start checkout. Please try again.", status_code=502, code="checkout_failed")
        return ok(data={"checkout_url": url}, message="Redirecting to secure checkout…")

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
    """Change plan.

    With Stripe configured, a paid tier returns a Checkout URL (the tier is
    activated by the webhook after payment); downgrading to Free cancels the
    Stripe subscription and applies immediately. Without Stripe, changes apply
    immediately (the instant-upgrade stub).
    """
    db_user = await session.get(User, user.id)

    # Downgrade / cancel is always immediate.
    if payload.tier == "free":
        if stripe_billing.stripe_enabled():
            await stripe_billing.cancel_subscription(db_user)
        db_user.tier = "free"
        db_user.stripe_subscription_id = None
        await session.commit()
        return ok(data={"tier": "free"}, message="Your plan was cancelled — you're back on Free.")

    if stripe_billing.stripe_enabled():
        try:
            url = await stripe_billing.create_subscription_checkout(db_user, payload.tier)
        except Exception:
            logger.exception("Stripe subscription checkout failed")
            return error("We couldn't start checkout. Please try again.", status_code=502, code="checkout_failed")
        return ok(data={"checkout_url": url}, message="Redirecting to secure checkout…")

    # Stub: apply immediately.
    db_user.tier = payload.tier
    await session.commit()
    return ok(data={"tier": payload.tier}, message=f"You're on {_TIER_NAMES[payload.tier]} now. Enjoy!")


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> object:
    """Stripe webhook — verifies the signature and applies subscription/token events.

    Public (no auth): Stripe calls it directly. Every event is signature-verified
    against STRIPE_WEBHOOK_SECRET before it can touch an account.
    """
    if not stripe_billing.stripe_enabled():
        return ok(message="Stripe is not configured.")
    payload = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe_billing.construct_event(payload, sig)
    except Exception:
        return error("Invalid webhook signature.", status_code=400, code="bad_signature")
    try:
        await stripe_billing.process_event(session, event)
    except Exception:
        logger.exception("Failed to process Stripe event")
        # 200 so Stripe doesn't hammer retries on a bug we've already logged.
    return ok(message="ok")
