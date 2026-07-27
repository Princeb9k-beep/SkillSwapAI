"""Learning-buddy shared streaks.

Invite a partner; once they accept, the pair keeps a shared streak that only
advances on days BOTH partners check in — BeReal-style mutual accountability.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Buddy, User
from ..responses import error, ok
from ..schemas import BuddyInvite
from ..skills.notifications import create_notification

router = APIRouter(prefix="/buddies", tags=["buddies"])


def _dict(b: Buddy, me_id: int, names: dict[int, str]) -> dict:
    partner_id = b.partner_id if b.inviter_id == me_id else b.inviter_id
    my_field = b.inviter_checked_on if b.inviter_id == me_id else b.partner_checked_on
    their_field = b.partner_checked_on if b.inviter_id == me_id else b.inviter_checked_on
    today = date.today()
    return {
        "id": b.id,
        "partner_id": partner_id,
        "partner_name": names.get(partner_id) or f"Learner #{partner_id}",
        "status": b.status,
        "streak": b.streak,
        "i_checked_in": my_field == today,
        "partner_checked_in": their_field == today,
        "is_inviter": b.inviter_id == me_id,
    }


@router.get("")
async def list_buddies(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    rows = (
        await session.execute(
            select(Buddy)
            .where(or_(Buddy.inviter_id == user.id, Buddy.partner_id == user.id))
            .where(Buddy.status != "ended")
            .order_by(Buddy.streak.desc(), Buddy.id.desc())
        )
    ).scalars().all()
    ids = {u for b in rows for u in (b.inviter_id, b.partner_id)}
    names = {}
    if ids:
        names = dict(
            (await session.execute(select(User.id, User.name).where(User.id.in_(ids)))).all()
        )
    return ok(data=[_dict(b, user.id, names) for b in rows])


@router.post("")
async def invite(
    payload: BuddyInvite,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Invite someone to be your learning buddy."""
    if payload.partner_id == user.id:
        return error("You can't buddy up with yourself.", status_code=400, code="invalid")
    partner = await session.get(User, payload.partner_id)
    if partner is None:
        return error("User not found.", status_code=404, code="not_found")
    # One active/pending pairing per pair.
    existing = (
        await session.execute(
            select(Buddy).where(
                Buddy.status != "ended",
                or_(
                    (Buddy.inviter_id == user.id) & (Buddy.partner_id == payload.partner_id),
                    (Buddy.inviter_id == payload.partner_id) & (Buddy.partner_id == user.id),
                ),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return error("You already have a buddy request with this person.", status_code=409, code="exists")

    b = Buddy(inviter_id=user.id, partner_id=payload.partner_id, status="pending")
    session.add(b)
    create_notification(
        session,
        payload.partner_id,
        type="meetup",
        title=f"{user.name or 'Someone'} wants to be your learning buddy",
        body="Accept to start a shared streak.",
        link="/buddies",
    )
    await session.commit()
    await session.refresh(b)
    names = {user.id: user.name or "", partner.id: partner.name or ""}
    return ok(data=_dict(b, user.id, names), message="Buddy request sent", status_code=201)


@router.post("/{buddy_id}/accept")
async def accept(
    buddy_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Accept a pending buddy request (only the invited partner)."""
    b = await session.get(Buddy, buddy_id)
    if b is None or b.partner_id != user.id or b.status != "pending":
        return error("Request not found.", status_code=404, code="not_found")
    b.status = "active"
    create_notification(
        session,
        b.inviter_id,
        type="meetup",
        title=f"{user.name or 'Your buddy'} accepted — you're learning buddies!",
        body="Check in each day to grow your shared streak.",
        link="/buddies",
    )
    await session.commit()
    return ok(data={"id": b.id, "status": b.status}, message="You're buddies now!")


@router.post("/{buddy_id}/checkin")
async def checkin(
    buddy_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Mark your daily check-in. The shared streak advances once both have
    checked in on the same day."""
    b = await session.get(Buddy, buddy_id)
    if b is None or user.id not in (b.inviter_id, b.partner_id) or b.status != "active":
        return error("Buddy not found.", status_code=404, code="not_found")
    today = date.today()
    if b.inviter_id == user.id:
        b.inviter_checked_on = today
    else:
        b.partner_checked_on = today

    advanced = False
    both_today = b.inviter_checked_on == today and b.partner_checked_on == today
    if both_today and b.last_advanced_on != today:
        if b.last_advanced_on == today - timedelta(days=1):
            b.streak = (b.streak or 0) + 1
        else:
            b.streak = 1
        b.last_advanced_on = today
        advanced = True
    await session.commit()
    return ok(
        data={"id": b.id, "streak": b.streak, "advanced": advanced, "both_today": both_today},
        message="Streak grew! 🔥" if advanced else "Checked in — waiting on your buddy.",
    )


@router.post("/{buddy_id}/end")
async def end(
    buddy_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    b = await session.get(Buddy, buddy_id)
    if b is None or user.id not in (b.inviter_id, b.partner_id):
        return error("Buddy not found.", status_code=404, code="not_found")
    b.status = "ended"
    await session.commit()
    return ok(message="Buddy pairing ended")
