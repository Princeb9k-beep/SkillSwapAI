"""Activity-feed helper: record public milestones (no commit — caller commits)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Activity


def record_activity(session: AsyncSession, user_id: int, kind: str, text: str) -> Activity:
    activity = Activity(user_id=user_id, kind=kind, text=text[:255])
    session.add(activity)
    return activity
