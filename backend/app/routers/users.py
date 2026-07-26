"""User profile endpoints (authenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user, user_is_admin
from ..models import Achievement, Skill, User
from ..responses import error, ok
from ..schemas import ProfileUpdate, UserOut
from ..skills.reputation import score_for

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> object:
    """Return the current (token-identified) user."""
    data = UserOut.model_validate(user).model_dump(mode="json")
    data["is_admin"] = user_is_admin(user)
    return ok(data=data)


@router.get("/{user_id}/profile")
async def public_profile(
    user_id: int,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Public-facing profile: gamification stats, skills, badges, reputation."""
    target = await session.get(User, user_id)
    if target is None:
        return error("User not found.", status_code=404, code="not_found")

    skills = (
        await session.execute(
            select(Skill).where(Skill.user_id == user_id, Skill.kind == "have")
        )
    ).scalars().all()
    badges = (
        await session.execute(
            select(Achievement)
            .where(Achievement.user_id == user_id)
            .order_by(Achievement.earned_at.desc())
        )
    ).scalars().all()
    reputation = await score_for(session, user_id)

    return ok(
        data={
            "id": target.id,
            "name": target.name or f"Learner #{target.id}",
            "goal": target.goal,
            "level": target.level,
            "xp": target.xp,
            "streak": target.streak,
            "tier": target.tier,
            "member_since": target.created_at.isoformat() if target.created_at else None,
            "skills": [
                {"name": s.name, "level": s.level, "verified": s.verified}
                for s in skills
            ],
            "badges": [
                {"code": b.code, "title": b.title, "description": b.description}
                for b in badges
            ],
            "reputation": reputation,
        }
    )


@router.patch("/me")
async def update_me(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Update the current user's name / goal / target income."""
    if payload.name is not None:
        user.name = payload.name
    if payload.goal is not None:
        user.goal = payload.goal
    if payload.target_income is not None:
        user.target_income = payload.target_income
    if payload.notify_messages is not None:
        user.notify_messages = payload.notify_messages
    if payload.notify_achievements is not None:
        user.notify_achievements = payload.notify_achievements
    if payload.notify_product is not None:
        user.notify_product = payload.notify_product
    if payload.daily_reminder is not None:
        user.daily_reminder = payload.daily_reminder
    if payload.onboarded is not None:
        user.onboarded = payload.onboarded
    await session.commit()
    return ok(
        data=UserOut.model_validate(user).model_dump(mode="json"),
        message="Profile updated",
    )


@router.delete("/me")
async def delete_me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Permanently delete the current account and all its data (cascades via
    ON DELETE CASCADE across skills, roadmaps, messages, notifications, etc.)."""
    await session.delete(user)
    await session.commit()
    return ok(message="Your account has been deleted.")
