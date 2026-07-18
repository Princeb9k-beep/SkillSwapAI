"""Roadmap endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Roadmap, User
from ..responses import error, ok
from ..schemas import RoadmapCreate
from ..skills.roadmap import generate_roadmap

router = APIRouter(prefix="/roadmap", tags=["roadmap"])


@router.post("")
async def create_roadmap(
    payload: RoadmapCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Generate and persist a learning roadmap for the current user."""
    content = await generate_roadmap(user.id, payload.goal, payload.current_skills)
    roadmap = Roadmap(user_id=user.id, goal=payload.goal, content=content)
    session.add(roadmap)
    await session.commit()
    # id is populated on commit (expire_on_commit=False); response needs no
    # server-generated columns, so skip an extra refresh round-trip.
    return ok(
        data={"id": roadmap.id, "goal": roadmap.goal, "content": roadmap.content},
        message="Roadmap generated",
    )


@router.get("")
async def latest_roadmap(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Return the user's most recent roadmap."""
    result = await session.execute(
        select(Roadmap)
        .where(Roadmap.user_id == user.id)
        .order_by(Roadmap.created_at.desc())
        .limit(1)
    )
    roadmap = result.scalar_one_or_none()
    if roadmap is None:
        return error("No roadmap yet. Generate one with POST /roadmap.",
                     status_code=404, code="not_found")
    return ok(data={"id": roadmap.id, "goal": roadmap.goal, "content": roadmap.content})
