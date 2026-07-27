"""1:1 session scheduling.

A host proposes a time to a partner; the guest confirms or declines; either can
cancel. Trial sessions are a short free intro. Each state change drops an in-app
notification (and email/push, best-effort).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..background import run_in_background
from ..database import get_session, get_sessionmaker
from ..deps import get_current_user
from ..mailer import send_event_email
from ..models import Session, User
from ..responses import error, ok
from ..schemas import SessionCreate, SessionRespond
from ..skills.notifications import create_notification

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _dict(s: Session, me_id: int, names: dict[int, str]) -> dict:
    partner_id = s.guest_id if s.host_id == me_id else s.host_id
    return {
        "id": s.id,
        "role": "host" if s.host_id == me_id else "guest",
        "partner_id": partner_id,
        "partner_name": names.get(partner_id) or f"Learner #{partner_id}",
        "skill": s.skill,
        "scheduled_at": s.scheduled_at.isoformat() if s.scheduled_at else None,
        "duration_min": s.duration_min,
        "is_trial": s.is_trial,
        "note": s.note,
        "status": s.status,
    }


@router.get("")
async def list_sessions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """My sessions (as host or guest), soonest first."""
    rows = (
        await session.execute(
            select(Session)
            .where(or_(Session.host_id == user.id, Session.guest_id == user.id))
            .where(Session.status.in_(["proposed", "confirmed"]))
            .order_by(Session.scheduled_at.asc())
        )
    ).scalars().all()
    ids = {u for s in rows for u in (s.host_id, s.guest_id)}
    names = {}
    if ids:
        names = dict(
            (await session.execute(select(User.id, User.name).where(User.id.in_(ids)))).all()
        )
    return ok(data=[_dict(s, user.id, names) for s in rows])


@router.post("")
async def propose(
    payload: SessionCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Propose a session time to a partner."""
    if payload.partner_id == user.id:
        return error("You can't book a session with yourself.", status_code=400, code="invalid")
    partner = await session.get(User, payload.partner_id)
    if partner is None:
        return error("User not found.", status_code=404, code="not_found")
    when = payload.scheduled_at
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if when <= datetime.now(timezone.utc):
        return error("Pick a time in the future.", status_code=400, code="past_time")

    s = Session(
        host_id=user.id,
        guest_id=payload.partner_id,
        skill=(payload.skill or "").strip() or None,
        scheduled_at=when,
        duration_min=15 if payload.is_trial else payload.duration_min,
        is_trial=payload.is_trial,
        note=(payload.note or "").strip() or None,
    )
    session.add(s)
    host_name = user.name or f"Learner #{user.id}"
    kind = "a free intro session" if payload.is_trial else "a session"
    create_notification(
        session,
        payload.partner_id,
        type="meetup",
        title=f"{host_name} proposed {kind}",
        body=f"{when.strftime('%b %d, %H:%M UTC')} · {s.duration_min} min",
        link="/sessions",
    )
    await session.commit()
    await session.refresh(s)

    if partner.notify_messages:
        title = f"{host_name} proposed {kind}"
        body = f"{when.strftime('%b %d, %H:%M UTC')} · {s.duration_min} min. Open SkillSwap to confirm."

        async def _notify():
            async with get_sessionmaker()() as bg:
                from ..skills.webpush import push_to_user

                try:
                    await push_to_user(bg, payload.partner_id, title=title, body=body, link="/sessions")
                except Exception:  # noqa: BLE001
                    pass
            try:
                await send_event_email(partner, "meetup", title, body, "/sessions")
            except Exception:  # noqa: BLE001
                pass

        run_in_background(_notify(), name="session-proposed")

    names = {user.id: host_name, partner.id: partner.name or f"Learner #{partner.id}"}
    return ok(data=_dict(s, user.id, names), message="Session proposed", status_code=201)


@router.post("/{session_id}/respond")
async def respond(
    session_id: int,
    payload: SessionRespond,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Guest confirms or declines a proposed session."""
    s = await session.get(Session, session_id)
    if s is None or s.guest_id != user.id:
        return error("Session not found.", status_code=404, code="not_found")
    if s.status != "proposed":
        return error("This session is already decided.", status_code=409, code="decided")
    s.status = "confirmed" if payload.accept else "declined"
    verb = "confirmed" if payload.accept else "declined"
    create_notification(
        session,
        s.host_id,
        type="meetup",
        title=f"{user.name or 'Your partner'} {verb} the session",
        body=s.scheduled_at.strftime("%b %d, %H:%M UTC") if s.scheduled_at else "",
        link="/sessions",
    )
    await session.commit()
    return ok(data={"id": s.id, "status": s.status}, message=f"Session {verb}")


@router.post("/{session_id}/cancel")
async def cancel(
    session_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Either participant cancels a session."""
    s = await session.get(Session, session_id)
    if s is None or user.id not in (s.host_id, s.guest_id):
        return error("Session not found.", status_code=404, code="not_found")
    s.status = "cancelled"
    other = s.guest_id if s.host_id == user.id else s.host_id
    create_notification(
        session,
        other,
        type="meetup",
        title=f"{user.name or 'Your partner'} cancelled a session",
        body="",
        link="/sessions",
    )
    await session.commit()
    return ok(data={"id": s.id, "status": s.status}, message="Session cancelled")
