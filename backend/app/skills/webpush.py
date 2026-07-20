"""Browser Web Push delivery (VAPID).

Sends push messages to a user's stored subscriptions via pywebpush. Everything
degrades gracefully: if VAPID keys aren't configured (or pywebpush isn't
installed), sending is a no-op and the app still works with in-app
notifications. Subscriptions that the push service reports as gone (404/410) are
pruned automatically.
"""

from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import PushSubscription

logger = logging.getLogger("skillswap")


def push_configured() -> bool:
    s = get_settings()
    return bool(s.vapid_public_key and s.vapid_private_key)


def _send_one(sub_info: dict, data: str) -> int:
    """Blocking send of one push. Returns the push service HTTP status (or 0 on
    a transport error). Import pywebpush lazily so a missing dep can't break boot."""
    from pywebpush import WebPushException, webpush

    settings = get_settings()
    try:
        webpush(
            subscription_info=sub_info,
            data=data,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
            timeout=10,
        )
        return 201
    except WebPushException as exc:
        return getattr(exc.response, "status_code", 0) or 0
    except Exception:  # pragma: no cover - network/edge failures
        return 0


async def push_to_user(
    session: AsyncSession,
    user_id: int,
    *,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> None:
    """Deliver a push to every subscription the user has (best-effort)."""
    if not push_configured():
        return

    subs = (
        await session.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
    ).scalars().all()
    if not subs:
        return

    data = json.dumps({"title": title, "body": body or "", "link": link or "/"})
    loop = asyncio.get_event_loop()
    dead: list[str] = []
    for sub in subs:
        info = {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }
        status = await loop.run_in_executor(None, _send_one, info, data)
        if status in (404, 410):
            dead.append(sub.endpoint)

    if dead:
        await session.execute(
            delete(PushSubscription).where(PushSubscription.endpoint.in_(dead))
        )
        await session.commit()
