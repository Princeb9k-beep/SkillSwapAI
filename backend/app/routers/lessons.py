"""Daily lessons endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import cache_get, cache_set, make_key
from ..database import get_session
from ..deps import get_current_user
from ..models import Lesson, User
from ..responses import error, ok
from ..schemas import LessonOut
from ..skills.lessons import generate_daily_lessons

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.get("/daily")
async def daily(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """
    Return today's lessons, generating and persisting them once per user/day.
    Progress + the generated set are cached in Redis (daily lesson caching).
    """
    day = (datetime.now(timezone.utc).date().toordinal())
    cache_key = make_key("lessons", user.id, day)

    # If we've already created today's lessons, return them.
    result = await session.execute(
        select(Lesson).where(Lesson.user_id == user.id, Lesson.day == day)
    )
    existing = result.scalars().all()
    if existing:
        return ok(data=[LessonOut.model_validate(l).model_dump() for l in existing])

    cached = await cache_get(cache_key)
    generated = cached or await generate_daily_lessons(
        user.goal or "grow my career", day
    )
    await cache_set(cache_key, generated)

    created: list[Lesson] = []
    for item in generated:
        lesson = Lesson(
            user_id=user.id,
            day=day,
            title=item.get("title", "Lesson"),
            content=item.get("content"),
        )
        session.add(lesson)
        created.append(lesson)
    await session.commit()
    for l in created:
        await session.refresh(l)
    return ok(
        data=[LessonOut.model_validate(l).model_dump() for l in created],
        message="Today's lessons",
    )


@router.post("/{lesson_id}/complete")
async def complete(
    lesson_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Mark a lesson complete (gamification progress)."""
    lesson = await session.get(Lesson, lesson_id)
    if lesson is None or lesson.user_id != user.id:
        return error("Lesson not found.", status_code=404, code="not_found")
    lesson.completed = True
    lesson.completed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(lesson)
    return ok(data=LessonOut.model_validate(lesson).model_dump(), message="Lesson completed")
