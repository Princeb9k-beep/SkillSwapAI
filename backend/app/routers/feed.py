"""Activity feed: recent learner milestones + kudos."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Activity, ActivityKudos, User
from ..responses import error, ok

router = APIRouter(prefix="/feed", tags=["feed"])

# Line-icon names (resolved to SVGs on the client), not emoji, for a cleaner look.
_VERBS = {
    "verified": "shieldCheck",
    "achievement": "medal",
    "level_up": "trending",
    "completion": "graduation",
    "streak": "flame",
}


@router.get("")
async def feed(
    limit: int = Query(default=30, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Most recent activity across the community, with kudos state for me."""
    rows = (
        await session.execute(
            select(Activity).order_by(Activity.created_at.desc(), Activity.id.desc()).limit(limit)
        )
    ).scalars().all()
    if not rows:
        return ok(data=[])

    user_ids = {a.user_id for a in rows}
    names = dict(
        (await session.execute(select(User.id, User.name).where(User.id.in_(user_ids)))).all()
    )
    my_kudos = {
        row[0]
        for row in (
            await session.execute(
                select(ActivityKudos.activity_id).where(
                    ActivityKudos.user_id == user.id,
                    ActivityKudos.activity_id.in_([a.id for a in rows]),
                )
            )
        ).all()
    }

    return ok(
        data=[
            {
                "id": a.id,
                "user_id": a.user_id,
                "name": names.get(a.user_id) or f"Learner #{a.user_id}",
                "kind": a.kind,
                "icon": _VERBS.get(a.kind, "sparkle"),
                "text": a.text,
                "kudos": a.kudos,
                "kudoed": a.id in my_kudos,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ]
    )


@router.post("/{activity_id}/kudos")
async def toggle_kudos(
    activity_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Give or take back kudos on an activity."""
    activity = await session.get(Activity, activity_id)
    if activity is None:
        return error("Activity not found.", status_code=404, code="not_found")
    existing = (
        await session.execute(
            select(ActivityKudos).where(
                ActivityKudos.activity_id == activity_id, ActivityKudos.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await session.execute(
            delete(ActivityKudos).where(ActivityKudos.id == existing.id)
        )
        activity.kudos = max(0, (activity.kudos or 0) - 1)
        kudoed = False
    else:
        session.add(ActivityKudos(activity_id=activity_id, user_id=user.id))
        activity.kudos = (activity.kudos or 0) + 1
        kudoed = True
    await session.commit()
    return ok(data={"id": activity_id, "kudos": activity.kudos, "kudoed": kudoed})
