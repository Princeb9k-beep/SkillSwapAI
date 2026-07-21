"""Safety & moderation: block/unblock users and report content.

Blocking is mutual in effect — a blocked pair is hidden from each other's
matches (see skills/matching.py) and can't message one another. Reports are
recorded for later review.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Block, Report, User
from ..responses import error, ok
from ..schemas import ReportCreate

router = APIRouter(tags=["moderation"])


async def blocked_ids(session: AsyncSession, user_id: int) -> set[int]:
    """Everyone in a block relationship with the user, in either direction."""
    rows = await session.execute(
        select(Block.blocker_id, Block.blocked_id).where(
            or_(Block.blocker_id == user_id, Block.blocked_id == user_id)
        )
    )
    ids: set[int] = set()
    for blocker, blocked in rows.all():
        ids.add(blocked if blocker == user_id else blocker)
    return ids


@router.get("/blocks")
async def list_blocks(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Users the current user has blocked."""
    rows = await session.execute(
        select(Block.blocked_id, User.name)
        .join(User, User.id == Block.blocked_id)
        .where(Block.blocker_id == user.id)
        .order_by(Block.created_at.desc())
    )
    data = [{"user_id": uid, "name": name or f"Learner #{uid}"} for uid, name in rows.all()]
    return ok(data=data)


@router.post("/blocks/{user_id}")
async def block_user(
    user_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Block another user."""
    if user_id == user.id:
        return error("You can't block yourself.", status_code=400, code="invalid")
    if await session.get(User, user_id) is None:
        return error("User not found.", status_code=404, code="not_found")
    exists = (
        await session.execute(
            select(Block).where(
                Block.blocker_id == user.id, Block.blocked_id == user_id
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(Block(blocker_id=user.id, blocked_id=user_id))
        await session.commit()
    return ok(message="User blocked")


@router.delete("/blocks/{user_id}")
async def unblock_user(
    user_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Unblock a user."""
    await session.execute(
        delete(Block).where(Block.blocker_id == user.id, Block.blocked_id == user_id)
    )
    await session.commit()
    return ok(message="User unblocked")


@router.post("/reports")
async def create_report(
    payload: ReportCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Report a user, message, or post for moderation review."""
    session.add(
        Report(
            reporter_id=user.id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            reason=payload.reason.strip(),
        )
    )
    await session.commit()
    return ok(message="Thanks — our team will review this.", status_code=201)
