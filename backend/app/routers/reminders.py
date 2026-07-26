"""Daily-reminder trigger endpoint.

An external scheduler (e.g. a Render Cron Job) calls POST /reminders/run once a
day with the shared X-Cron-Secret header. Admins can also trigger it manually.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_session
from ..deps import get_optional_user, user_is_admin
from ..models import User
from ..responses import error, ok
from ..skills.reminders import run_daily_reminders

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.post("/run")
async def run(
    x_cron_secret: str | None = Header(default=None),
    user: User | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Trigger the daily reminder job. Authorized by the cron secret or an admin."""
    secret = get_settings().cron_secret
    authorized = (secret and x_cron_secret == secret) or (user and user_is_admin(user))
    if not authorized:
        return error("Not authorized to run reminders.", status_code=403, code="forbidden")
    sent = await run_daily_reminders(session)
    return ok(data={"sent": sent}, message=f"Reminders sent to {sent} user(s).")
