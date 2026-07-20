"""In-app notifications: list, unread count, and mark-as-read (spec: real
notifications). Rows are created by events elsewhere (messages, achievements,
signup) via `skills.notifications.create_notification`."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Notification, User
from ..responses import error, ok

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "read": n.read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("")
async def list_notifications(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Recent notifications (newest first) with the current unread count."""
    rows = (
        await session.execute(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(50)
        )
    ).scalars().all()
    unread = sum(1 for n in rows if not n.read)
    return ok(data=[_dict(n) for n in rows], meta={"unread": unread})


@router.get("/unread/count")
async def unread_count(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Unread notification count (for the nav bell badge)."""
    total = (
        await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.read.is_(False))
        )
    ).scalar_one()
    return ok(data={"unread": int(total or 0)})


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Mark a single notification read."""
    note = await session.get(Notification, notification_id)
    if note is None or note.user_id != user.id:
        return error("Notification not found.", status_code=404, code="not_found")
    note.read = True
    await session.commit()
    return ok(message="Marked read")


@router.post("/read-all")
async def mark_all_read(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Mark every notification read."""
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read.is_(False))
        .values(read=True)
    )
    await session.commit()
    return ok(message="All caught up")
