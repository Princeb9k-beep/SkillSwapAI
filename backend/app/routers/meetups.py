"""Local Meetups (spec §3.5): opt-in study meetups others can RSVP to.

Safety by design: everything is opt-in, locations are free-text and public
(no precise geolocation stored), and only the host can cancel their meetup.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Meetup, MeetupRsvp, User
from ..responses import error, ok
from ..schemas import MeetupCreate

router = APIRouter(prefix="/meetups", tags=["meetups"])


def _meetup_dict(m: Meetup, host_name: str | None, count: int, joined: bool) -> dict:
    return {
        "id": m.id,
        "title": m.title,
        "description": m.description,
        "location": m.location,
        "starts_at": m.starts_at.isoformat() if m.starts_at else None,
        "capacity": m.capacity,
        "host_id": m.host_id,
        "host_name": host_name or f"Learner #{m.host_id}",
        "attendee_count": count,
        "joined": joined,
        "is_full": bool(m.capacity) and count >= m.capacity,
    }


@router.get("")
async def list_meetups(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Upcoming meetups (soonest first) with attendee counts + my RSVP flag."""
    now = datetime.now(timezone.utc)
    rows = await session.execute(
        select(Meetup, User.name)
        .join(User, User.id == Meetup.host_id)
        .where(Meetup.starts_at >= now)
        .order_by(Meetup.starts_at.asc())
        .limit(100)
    )
    meetups = rows.all()
    counts = dict(
        (await session.execute(
            select(MeetupRsvp.meetup_id, func.count()).group_by(MeetupRsvp.meetup_id)
        )).all()
    )
    mine = {
        r[0]
        for r in (await session.execute(
            select(MeetupRsvp.meetup_id).where(MeetupRsvp.user_id == user.id)
        )).all()
    }
    data = [
        _meetup_dict(m, host_name, counts.get(m.id, 0), m.id in mine)
        for m, host_name in meetups
    ]
    return ok(data=data)


@router.post("")
async def create_meetup(
    payload: MeetupCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Host a meetup; the host is auto-RSVP'd."""
    meetup = Meetup(
        host_id=user.id,
        title=payload.title.strip(),
        description=payload.description,
        location=payload.location.strip() or "Online",
        starts_at=payload.starts_at,
        capacity=payload.capacity,
    )
    session.add(meetup)
    await session.flush()
    session.add(MeetupRsvp(meetup_id=meetup.id, user_id=user.id))
    await session.commit()
    return ok(
        data=_meetup_dict(meetup, user.name, 1, True),
        message="Meetup created",
        status_code=201,
    )


async def _count(session: AsyncSession, meetup_id: int) -> int:
    return int(
        (await session.execute(
            select(func.count()).select_from(MeetupRsvp).where(
                MeetupRsvp.meetup_id == meetup_id
            )
        )).scalar_one()
    )


@router.post("/{meetup_id}/rsvp")
async def rsvp(
    meetup_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """RSVP to a meetup (respecting capacity)."""
    meetup = await session.get(Meetup, meetup_id)
    if meetup is None:
        return error("Meetup not found.", status_code=404, code="not_found")
    already = (
        await session.execute(
            select(MeetupRsvp).where(
                MeetupRsvp.meetup_id == meetup_id, MeetupRsvp.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if already is not None:
        return ok(message="Already going")
    if meetup.capacity and await _count(session, meetup_id) >= meetup.capacity:
        return error("This meetup is full.", status_code=409, code="full")
    session.add(MeetupRsvp(meetup_id=meetup_id, user_id=user.id))
    await session.commit()
    return ok(message="You're going!")


@router.post("/{meetup_id}/cancel")
async def cancel_rsvp(
    meetup_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Cancel your RSVP."""
    from sqlalchemy import delete

    await session.execute(
        delete(MeetupRsvp).where(
            MeetupRsvp.meetup_id == meetup_id, MeetupRsvp.user_id == user.id
        )
    )
    await session.commit()
    return ok(message="RSVP cancelled")


@router.delete("/{meetup_id}")
async def delete_meetup(
    meetup_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Delete a meetup (host only)."""
    meetup = await session.get(Meetup, meetup_id)
    if meetup is None:
        return error("Meetup not found.", status_code=404, code="not_found")
    if meetup.host_id != user.id:
        return error("Only the host can delete this meetup.", status_code=403, code="forbidden")
    await session.delete(meetup)
    await session.commit()
    return ok(message="Meetup deleted")
