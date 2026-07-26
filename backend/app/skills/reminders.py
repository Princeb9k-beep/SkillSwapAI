"""Daily learning reminders.

Finds users who opted into a daily nudge and haven't been reminded today, then
sends an in-app notification (+ push + email, best-effort) pointing at today's
lesson. Meant to be triggered once a day by an external scheduler hitting
POST /reminders/run; idempotent within a day via `last_reminded_on`.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..mailer import send_event_email
from ..models import User
from .notifications import create_notification
from .webpush import push_to_user

logger = logging.getLogger("skillswap.reminders")

_TITLE = "Keep your streak alive 🔥"
_BODY = "Your next lesson is ready — a few minutes today keeps you moving toward your goal."
_LINK = "/lessons"


async def run_daily_reminders(session: AsyncSession) -> int:
    """Send today's reminder to opted-in users not yet reminded today. Returns
    the number of users nudged."""
    today = date.today()
    users = (
        await session.execute(
            select(User).where(
                User.daily_reminder.is_(True),
                (User.last_reminded_on.is_(None)) | (User.last_reminded_on != today),
            )
        )
    ).scalars().all()

    sent = 0
    for user in users:
        create_notification(
            session, user.id, type="reminder", title=_TITLE, body=_BODY, link=_LINK
        )
        user.last_reminded_on = today
        sent += 1
    await session.commit()

    # External deliveries after the DB is consistent (best-effort).
    for user in users:
        try:
            await push_to_user(session, user.id, title=_TITLE, body=_BODY, link=_LINK)
        except Exception:  # noqa: BLE001
            pass
        try:
            await send_event_email(user, "reminder", _TITLE, _BODY, _LINK)
        except Exception:  # noqa: BLE001
            pass

    logger.info("Daily reminders sent to %d user(s)", sent)
    return sent
