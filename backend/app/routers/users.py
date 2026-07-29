"""User profile endpoints (authenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user, user_is_admin
from ..models import Achievement, Endorsement, Skill, User
from ..responses import error, ok
from ..schemas import EndorseRequest, ProfileUpdate, UserOut
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

    # Endorsement counts per skill (normalized name -> count).
    endo_rows = (
        await session.execute(
            select(Endorsement.skill_normalized, func.count())
            .where(Endorsement.subject_id == user_id)
            .group_by(Endorsement.skill_normalized)
        )
    ).all()
    endo = {name: int(n) for name, n in endo_rows}

    return ok(
        data={
            "id": target.id,
            "name": target.name or f"Learner #{target.id}",
            "goal": target.goal,
            "level": target.level,
            "xp": target.xp,
            "streak": target.streak,
            "tier": target.tier,
            "availability_note": target.availability_note,
            "member_since": target.created_at.isoformat() if target.created_at else None,
            "skills": [
                {
                    "name": s.name,
                    "level": s.level,
                    "verified": s.verified,
                    "endorsements": endo.get((s.name or "").lower(), 0),
                }
                for s in skills
            ],
            "badges": [
                {"code": b.code, "title": b.title, "description": b.description}
                for b in badges
            ],
            "reputation": reputation,
        }
    )


@router.post("/{user_id}/endorse")
async def endorse(
    user_id: int,
    payload: EndorseRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Endorse another learner for a skill (one endorsement per skill)."""
    if user_id == user.id:
        return error("You can't endorse yourself.", status_code=400, code="invalid")
    target = await session.get(User, user_id)
    if target is None:
        return error("User not found.", status_code=404, code="not_found")
    skill = payload.skill.strip()
    norm = skill.lower()
    existing = (
        await session.execute(
            select(Endorsement).where(
                Endorsement.endorser_id == user.id,
                Endorsement.subject_id == user_id,
                Endorsement.skill_normalized == norm,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return error("You've already endorsed this skill.", status_code=409, code="exists")
    session.add(
        Endorsement(
            endorser_id=user.id, subject_id=user_id, skill=skill, skill_normalized=norm
        )
    )
    await session.commit()
    count = (
        await session.execute(
            select(func.count())
            .select_from(Endorsement)
            .where(Endorsement.subject_id == user_id, Endorsement.skill_normalized == norm)
        )
    ).scalar_one()
    return ok(data={"skill": skill, "endorsements": int(count)}, message="Endorsed!")


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
    if payload.availability_note is not None:
        user.availability_note = payload.availability_note.strip() or None
    if payload.timezone is not None:
        user.timezone = payload.timezone.strip() or "UTC"
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
