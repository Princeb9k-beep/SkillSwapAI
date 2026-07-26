"""Global search across people, communities, and Academy courses."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Community, Skill, User
from ..responses import ok
from ..skills import catalog

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=8, ge=1, le=25),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Search people (by name or skill), communities, and Academy courses."""
    term = q.strip()
    like = f"%{term}%"
    norm = f"%{term.lower()}%"

    # People — name match OR they can teach a matching skill (exclude self).
    people_rows = (
        await session.execute(
            select(User)
            .distinct()
            .outerjoin(Skill, and_(Skill.user_id == User.id, Skill.kind == "have"))
            .where(User.id != user.id)
            .where(or_(User.name.ilike(like), Skill.name_normalized.ilike(norm)))
            .limit(limit)
        )
    ).scalars().all()

    ids = [u.id for u in people_rows]
    skills_by_user: dict[int, list[str]] = {}
    if ids:
        srows = (
            await session.execute(
                select(Skill).where(Skill.user_id.in_(ids), Skill.kind == "have")
            )
        ).scalars().all()
        for s in srows:
            skills_by_user.setdefault(s.user_id, []).append(s.name)

    people = [
        {
            "id": u.id,
            "name": u.name or f"Learner #{u.id}",
            "level": u.level,
            "skills": skills_by_user.get(u.id, [])[:6],
        }
        for u in people_rows
    ]

    # Communities — name/topic/description match.
    comm_rows = (
        await session.execute(
            select(Community)
            .where(
                or_(
                    Community.name.ilike(like),
                    Community.topic.ilike(like),
                    Community.description.ilike(like),
                )
            )
            .limit(limit)
        )
    ).scalars().all()
    communities = [
        {"id": c.id, "name": c.name, "topic": c.topic, "description": c.description}
        for c in comm_rows
    ]

    # Academy — catalog is in code; filter by title/category/summary.
    t = term.lower()
    courses = [
        {
            "slug": p["slug"],
            "title": p["title"],
            "category": p["category"],
            "difficulty": p["difficulty"],
        }
        for p in catalog.list_paths()
        if t in p["title"].lower()
        or t in p["category"].lower()
        or t in p.get("summary", "").lower()
    ][:limit]

    total = len(people) + len(communities) + len(courses)
    return ok(
        data={"people": people, "communities": communities, "courses": courses},
        meta={"total": total, "query": term},
    )
