"""AI Coach endpoints (spec §2.4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import CoachMessage, User
from ..responses import ok
from ..schemas import CoachChat
from ..skills.coach import coach_reply

from ..plans import enforce_ai_quota

router = APIRouter(prefix="/coach", tags=["coach"])


@router.get("/history")
async def history(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Return the user's coach conversation (oldest first)."""
    rows = await session.execute(
        select(CoachMessage)
        .where(CoachMessage.user_id == user.id)
        .order_by(CoachMessage.id.asc())
    )
    messages = [
        {"role": m.role, "content": m.content} for m in rows.scalars().all()
    ]
    return ok(data=messages)


@router.post("/chat", dependencies=[Depends(enforce_ai_quota)])
async def chat_endpoint(
    payload: CoachChat,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Send a message to the coach and get a reply."""
    reply = await coach_reply(session, user, payload.message.strip())
    await session.commit()
    return ok(data={"reply": reply}, message="Coach replied")


@router.delete("/history")
async def clear(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Clear the coach conversation."""
    await session.execute(delete(CoachMessage).where(CoachMessage.user_id == user.id))
    await session.commit()
    return ok(message="Conversation cleared")
