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
from ..deps import get_current_user, require_admin
from ..models import Block, CommunityPost, Message, Report, User
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


# --- Moderator dashboard (admin only) ------------------------------------
async def _describe_target(session: AsyncSession, target_type: str, target_id: int) -> str:
    """Best-effort human-readable summary of what was reported."""
    if target_type == "user":
        u = await session.get(User, target_id)
        return f"User: {u.name or u.email}" if u else "User (deleted)"
    if target_type == "message":
        m = await session.get(Message, target_id)
        return f"Message: “{m.body[:120]}”" if m else "Message (deleted)"
    if target_type == "post":
        p = await session.get(CommunityPost, target_id)
        return f"Post: “{p.body[:120]}”" if p else "Post (deleted)"
    return target_type


@router.get("/admin/reports")
async def admin_list_reports(
    status: str = "open",
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> object:
    """List reports for moderation (admins only). `status`=open|all."""
    stmt = (
        select(Report, User.name)
        .join(User, User.id == Report.reporter_id)
        .order_by(Report.created_at.desc())
        .limit(200)
    )
    if status == "open":
        stmt = stmt.where(Report.status == "open")
    rows = (await session.execute(stmt)).all()
    data = []
    for r, reporter_name in rows:
        data.append(
            {
                "id": r.id,
                "reporter_name": reporter_name or f"Learner #{r.reporter_id}",
                "target_type": r.target_type,
                "target_id": r.target_id,
                "target_summary": await _describe_target(session, r.target_type, r.target_id),
                "reason": r.reason,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return ok(data=data)


@router.post("/admin/reports/{report_id}/resolve")
async def admin_resolve_report(
    report_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Mark a report reviewed (admins only)."""
    report = await session.get(Report, report_id)
    if report is None:
        return error("Report not found.", status_code=404, code="not_found")
    report.status = "reviewed"
    await session.commit()
    return ok(message="Report resolved")
