"""Direct messaging between users (spec §2.3).

1:1 conversations derived from a flat `messages` table. Threads list the latest
message per partner with an unread badge; opening a conversation marks the
partner's messages as read. Real-time delivery can later layer on the same
WebSocket hub pattern used by practice rooms; this REST surface is the durable
store of record.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Message, User
from ..responses import error, ok
from ..schemas import MessageCreate
from ..skills.notifications import create_notification
from ..skills.webpush import push_to_user

router = APIRouter(prefix="/messages", tags=["messages"])


def _msg_dict(m: Message, me_id: int) -> dict:
    return {
        "id": m.id,
        "body": m.body,
        "mine": m.sender_id == me_id,
        "read": m.read,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.get("/threads")
async def list_threads(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """One entry per conversation partner: their name, the latest message, and
    how many of their messages to me are still unread (newest thread first)."""
    rows = (
        await session.execute(
            select(Message)
            .where(or_(Message.sender_id == user.id, Message.recipient_id == user.id))
            .order_by(Message.created_at.desc(), Message.id.desc())
        )
    ).scalars().all()

    threads: dict[int, dict] = {}
    for m in rows:
        partner_id = m.recipient_id if m.sender_id == user.id else m.sender_id
        t = threads.get(partner_id)
        if t is None:
            t = {
                "partner_id": partner_id,
                "last_message": m.body,
                "last_at": m.created_at.isoformat() if m.created_at else None,
                "last_mine": m.sender_id == user.id,
                "unread": 0,
            }
            threads[partner_id] = t
        # rows are newest-first, so the first seen per partner is the latest.
        if m.recipient_id == user.id and not m.read:
            t["unread"] += 1

    if threads:
        names = dict(
            (
                await session.execute(
                    select(User.id, User.name).where(User.id.in_(list(threads.keys())))
                )
            ).all()
        )
        for pid, t in threads.items():
            t["partner_name"] = names.get(pid) or f"Learner #{pid}"

    data = sorted(threads.values(), key=lambda t: t["last_at"] or "", reverse=True)
    return ok(data=data)


@router.get("/{partner_id}")
async def conversation(
    partner_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Full conversation with a partner (oldest first). Marks their unread
    messages to me as read as a side effect of opening the thread."""
    partner = await session.get(User, partner_id)
    if partner is None:
        return error("User not found.", status_code=404, code="not_found")

    await session.execute(
        update(Message)
        .where(
            and_(
                Message.sender_id == partner_id,
                Message.recipient_id == user.id,
                Message.read.is_(False),
            )
        )
        .values(read=True)
    )
    await session.commit()

    rows = (
        await session.execute(
            select(Message)
            .where(
                or_(
                    and_(Message.sender_id == user.id, Message.recipient_id == partner_id),
                    and_(Message.sender_id == partner_id, Message.recipient_id == user.id),
                )
            )
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
    ).scalars().all()

    return ok(
        data={
            "partner_id": partner_id,
            "partner_name": partner.name or f"Learner #{partner_id}",
            "messages": [_msg_dict(m, user.id) for m in rows],
        }
    )


@router.post("/{partner_id}")
async def send_message(
    partner_id: int,
    payload: MessageCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Send a message to another user."""
    if partner_id == user.id:
        return error("You can't message yourself.", status_code=400, code="invalid")
    partner = await session.get(User, partner_id)
    if partner is None:
        return error("User not found.", status_code=404, code="not_found")

    from .moderation import blocked_ids  # local import avoids a cycle

    if partner_id in await blocked_ids(session, user.id):
        return error("You can't message this user.", status_code=403, code="blocked")

    message = Message(sender_id=user.id, recipient_id=partner_id, body=payload.body.strip())
    session.add(message)

    # Notify the recipient (if they haven't muted message alerts).
    link = f"/messages?to={user.id}&name={quote(user.name or f'Learner #{user.id}')}"
    if partner.notify_messages:
        sender_name = user.name or f"Learner #{user.id}"
        create_notification(
            session,
            partner_id,
            type="message",
            title=f"New message from {sender_name}",
            body=message.body,
            link=link,
        )

    await session.commit()

    # Best-effort browser push to the recipient's devices (no-op if unconfigured).
    if partner.notify_messages:
        try:
            await push_to_user(
                session,
                partner_id,
                title=f"New message from {user.name or 'a partner'}",
                body=message.body,
                link=link,
            )
        except Exception:  # never let push failures break sending
            pass

    return ok(data=_msg_dict(message, user.id), message="Sent", status_code=201)


@router.get("/unread/count")
async def unread_count(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Total unread messages across all conversations (for a nav badge)."""
    total = (
        await session.execute(
            select(func.count())
            .select_from(Message)
            .where(Message.recipient_id == user.id, Message.read.is_(False))
        )
    ).scalar_one()
    return ok(data={"unread": int(total or 0)})
