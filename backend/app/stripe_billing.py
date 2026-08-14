"""Stripe payments — Checkout sessions + webhook handling.

Active only when ``STRIPE_SECRET_KEY`` is set; otherwise the billing router keeps
its instant-upgrade stub so dev and free deployments work with no payment
provider (same graceful-degradation pattern as SMTP / Groq / Redis).

Prices are built inline from the app's own plan/pack catalog (``price_data``), so
there's nothing to pre-create in the Stripe dashboard beyond the API keys and a
webhook — the amounts always match ``plans.py``.
"""

from __future__ import annotations

import asyncio
import logging

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import User
from .plans import PLANS, TOKEN_PACKS, add_purchased_tokens

logger = logging.getLogger("skillswap.billing")


def stripe_enabled() -> bool:
    return get_settings().stripe_configured


def _client() -> None:
    """Point the Stripe SDK at the configured key (idempotent)."""
    stripe.api_key = get_settings().stripe_secret_key


def _urls() -> tuple[str, str]:
    base = get_settings().frontend_url.rstrip("/")
    return f"{base}/plans?checkout=success", f"{base}/plans?checkout=cancel"


async def create_subscription_checkout(user: User, tier: str) -> str:
    """Create a recurring Checkout Session for a Pro/Elite subscription; return its URL."""
    plan = next((p for p in PLANS if p["tier"] == tier), None)
    if plan is None or plan["price_cents"] <= 0:
        raise ValueError("That plan can't be purchased.")
    _client()
    success_url, cancel_url = _urls()

    def _create():
        return stripe.checkout.Session.create(
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(user.id),
            customer=user.stripe_customer_id or None,
            customer_email=None if user.stripe_customer_id else user.email,
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": plan["price_cents"],
                        "recurring": {"interval": "month"},
                        "product_data": {"name": f"SkillSwap AI — {plan['name']}"},
                    },
                }
            ],
            metadata={"user_id": str(user.id), "kind": "subscription", "tier": tier},
            subscription_data={"metadata": {"user_id": str(user.id), "tier": tier}},
        )

    session = await asyncio.to_thread(_create)
    return session.url


async def create_pack_checkout(user: User, pack_id: str) -> str:
    """Create a one-time Checkout Session for an AI-token pack; return its URL."""
    pack = next((p for p in TOKEN_PACKS if p["id"] == pack_id), None)
    if pack is None:
        raise ValueError("Unknown token pack.")
    _client()
    success_url, cancel_url = _urls()

    def _create():
        return stripe.checkout.Session.create(
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(user.id),
            customer=user.stripe_customer_id or None,
            customer_email=None if user.stripe_customer_id else user.email,
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": pack["price_cents"],
                        "product_data": {"name": f"{pack['tokens']:,} AI tokens — {pack['name']}"},
                    },
                }
            ],
            metadata={
                "user_id": str(user.id),
                "kind": "tokens",
                "pack": pack_id,
                "tokens": str(pack["tokens"]),
            },
        )

    session = await asyncio.to_thread(_create)
    return session.url


async def cancel_subscription(user: User) -> None:
    """Cancel the user's active Stripe subscription, if any (best-effort)."""
    if not user.stripe_subscription_id:
        return
    _client()
    sub_id = user.stripe_subscription_id
    try:
        await asyncio.to_thread(stripe.Subscription.delete, sub_id)
    except Exception:  # pragma: no cover - network/state; downgrade locally regardless
        logger.warning("Could not cancel Stripe subscription %s", sub_id)


def construct_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Verify a webhook payload and return the parsed event. Raises on bad signature."""
    secret = get_settings().stripe_webhook_secret
    return stripe.Webhook.construct_event(payload, sig_header, secret)


async def _user_by_id(session: AsyncSession, user_id: str | None) -> User | None:
    if not user_id:
        return None
    try:
        return await session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


async def process_event(session: AsyncSession, event: dict) -> None:
    """Apply a verified Stripe event to the user's account (idempotent-ish)."""
    etype = event.get("type")
    obj = event.get("data", {}).get("object", {})

    if etype == "checkout.session.completed":
        meta = obj.get("metadata") or {}
        user = await _user_by_id(session, meta.get("user_id") or obj.get("client_reference_id"))
        if user is None:
            return
        if meta.get("kind") == "subscription":
            user.tier = meta.get("tier", user.tier)
            if obj.get("customer"):
                user.stripe_customer_id = obj["customer"]
            if obj.get("subscription"):
                user.stripe_subscription_id = obj["subscription"]
            await session.commit()
            logger.info("Activated %s subscription for user %s", user.tier, user.id)
        elif meta.get("kind") == "tokens":
            tokens = int(meta.get("tokens", "0") or 0)
            if obj.get("customer"):
                user.stripe_customer_id = obj["customer"]
            if tokens > 0:
                await add_purchased_tokens(session, user, tokens)
            await session.commit()
            logger.info("Credited %d tokens to user %s", tokens, user.id)

    elif etype in ("customer.subscription.deleted", "customer.subscription.canceled"):
        # A subscription ended (cancel / non-payment) -> back to Free.
        sub_id = obj.get("id")
        row = await session.execute(
            select(User).where(User.stripe_subscription_id == sub_id)
        )
        user = row.scalar_one_or_none()
        if user is not None:
            user.tier = "free"
            user.stripe_subscription_id = None
            await session.commit()
            logger.info("Subscription ended — user %s back on Free", user.id)
