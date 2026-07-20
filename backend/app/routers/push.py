"""Web Push subscription management (spec: browser push notifications).

The browser subscribes with the VAPID public key and posts its subscription
here; the server stores it and later pushes to it (see skills/webpush.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_session
from ..deps import get_current_user
from ..models import PushSubscription, User
from ..responses import error, ok
from ..schemas import PushSubscribe, PushUnsubscribe

router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key")
async def vapid_public_key(user: User = Depends(get_current_user)) -> object:
    """Return the VAPID public key the browser needs to subscribe (null if
    push isn't configured on the server)."""
    key = get_settings().vapid_public_key or None
    return ok(data={"public_key": key})


@router.post("/subscribe")
async def subscribe(
    payload: PushSubscribe,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Store (or refresh) this device's push subscription."""
    keys = payload.keys or {}
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    if not p256dh or not auth:
        return error("Subscription is missing encryption keys.", status_code=422, code="invalid")

    existing = (
        await session.execute(
            select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.user_id = user.id
        existing.p256dh = p256dh
        existing.auth = auth
    else:
        session.add(
            PushSubscription(
                user_id=user.id, endpoint=payload.endpoint, p256dh=p256dh, auth=auth
            )
        )
    await session.commit()
    return ok(message="Subscribed", status_code=201)


@router.post("/unsubscribe")
async def unsubscribe(
    payload: PushUnsubscribe,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Remove this device's push subscription."""
    await session.execute(
        delete(PushSubscription).where(
            PushSubscription.endpoint == payload.endpoint,
            PushSubscription.user_id == user.id,
        )
    )
    await session.commit()
    return ok(message="Unsubscribed")
