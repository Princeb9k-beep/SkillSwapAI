"""Skill CRUD — the user's "have" and "want" skills that drive matching."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Skill, User
from ..responses import error, ok
from ..schemas import SkillCreate, SkillOut

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def list_skills(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """List the current user's skills (both 'have' and 'want')."""
    result = await session.execute(
        select(Skill).where(Skill.user_id == user.id).order_by(Skill.id)
    )
    skills = result.scalars().all()
    return ok(data=[SkillOut.model_validate(s).model_dump() for s in skills])


@router.post("")
async def add_skill(
    payload: SkillCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Add a 'have' or 'want' skill. De-duplicates on (kind, normalized name)."""
    normalized = payload.name.strip().lower()
    if not normalized:
        return error("Skill name can't be empty.", status_code=422, code="invalid")

    existing = await session.execute(
        select(Skill).where(
            Skill.user_id == user.id,
            Skill.kind == payload.kind,
            Skill.name_normalized == normalized,
        )
    )
    dupe = existing.scalar_one_or_none()
    if dupe is not None:
        return ok(
            data=SkillOut.model_validate(dupe).model_dump(),
            message="You already have that skill.",
        )

    skill = Skill(
        user_id=user.id,
        name=payload.name.strip(),
        name_normalized=normalized,
        kind=payload.kind,
        category=payload.category,
        level=payload.level,
    )
    session.add(skill)
    await session.commit()
    return ok(
        data=SkillOut.model_validate(skill).model_dump(),
        message="Skill added",
        status_code=201,
    )


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Remove one of the current user's skills."""
    skill = await session.get(Skill, skill_id)
    if skill is None or skill.user_id != user.id:
        return error("Skill not found.", status_code=404, code="not_found")
    await session.delete(skill)
    await session.commit()
    return ok(message="Skill removed")
