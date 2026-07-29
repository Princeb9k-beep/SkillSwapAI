"""Skill CRUD — the user's "have" and "want" skills that drive matching."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Skill, User
from ..responses import error, ok
from ..schemas import SkillCreate, SkillOut
from ..skill_catalog import SKILL_CATALOG

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/discover")
async def discover_skills(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """A personalized, TikTok-style feed of skills to explore.

    Returns the curated catalog annotated with (a) the user's current status for
    each skill ("have" / "want" / null) and (b) a real learner count computed from
    how many distinct users on the platform list it as a "have" skill. New skills
    the user doesn't have yet float to the top so the feed feels like discovery.
    """
    # The user's own skills, keyed by normalized name → kind.
    mine = {
        row[0]: row[1]
        for row in (
            await session.execute(
                select(Skill.name_normalized, Skill.kind).where(Skill.user_id == user.id)
            )
        ).all()
    }

    # Real "learners" counts: distinct users who list each skill as a "have".
    counts = {
        row[0]: row[1]
        for row in (
            await session.execute(
                select(Skill.name_normalized, func.count(func.distinct(Skill.user_id)))
                .where(Skill.kind == "have")
                .group_by(Skill.name_normalized)
            )
        ).all()
    }

    items = []
    for spec in SKILL_CATALOG:
        norm = spec["name"].strip().lower()
        status = mine.get(norm)  # "have", "want", or None
        items.append(
            {
                "name": spec["name"],
                "category": spec["category"],
                "emoji": spec["emoji"],
                "blurb": spec["blurb"],
                "hook": spec["hook"],
                "difficulty": spec["difficulty"],
                "learners": counts.get(norm, 0),
                "status": status,
            }
        )

    # Discovery order: brand-new skills first, then "want", then "have"; within a
    # tier, more-popular skills lead.
    rank = {None: 0, "want": 1, "have": 2}
    items.sort(key=lambda i: (rank.get(i["status"], 0), -i["learners"]))
    return ok(data=items)


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
