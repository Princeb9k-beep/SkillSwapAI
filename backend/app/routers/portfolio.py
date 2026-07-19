"""
Portfolio Builder (spec §3.2) — assembles the user's skills, verified badges,
achievements, and projects into one shareable profile. Read-only aggregation.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Achievement, Project, Skill, User
from ..responses import ok

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("")
async def portfolio(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Aggregate the current user's public-facing profile."""
    skills = (
        await session.execute(select(Skill).where(Skill.user_id == user.id))
    ).scalars().all()
    achievements = (
        await session.execute(
            select(Achievement)
            .where(Achievement.user_id == user.id)
            .order_by(Achievement.earned_at.desc())
        )
    ).scalars().all()
    projects = (
        await session.execute(
            select(Project)
            .where(Project.user_id == user.id)
            .order_by(Project.created_at.desc())
        )
    ).scalars().all()

    have = [
        {"name": s.name, "verified": s.verified, "level": s.level}
        for s in skills
        if s.kind == "have"
    ]
    want = [s.name for s in skills if s.kind == "want"]

    return ok(
        data={
            "name": user.name or f"Learner #{user.id}",
            "goal": user.goal,
            "target_income": user.target_income,
            "level": user.level,
            "xp": user.xp,
            "streak": user.streak,
            "verified_count": sum(1 for s in have if s["verified"]),
            "skills_have": have,
            "skills_want": want,
            "achievements": [
                {"title": a.title, "description": a.description} for a in achievements
            ],
            "projects": [
                {
                    "title": p.title,
                    "description": p.description,
                    "difficulty": p.difficulty,
                    "status": p.status,
                }
                for p in projects
            ],
        }
    )
