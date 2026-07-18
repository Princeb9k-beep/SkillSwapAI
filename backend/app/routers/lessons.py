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

    `day` is a friendly 1-based counter (day 1, 2, 3…) derived from how many
    distinct calendar days the user has studied — not a raw date ordinal. The
    generated content is cached in Redis keyed by the calendar day so repeat
    calls don't re-hit Groq.
    """
    today = datetime.now(timezone.utc).date()
    cache_key = make_key("lessons", user.id, today.toordinal())

    # Single read of the user's lessons; derive both "today's set" and the
    # day counter in one pass (no per-row refreshes, no date SQL).
    result = await session.execute(
        select(Lesson).where(Lesson.user_id == user.id).order_by(Lesson.id)
    )
    lessons = result.scalars().all()
    study_dates = {l.created_at.date() for l in lessons if l.created_at}

    todays = [l for l in lessons if l.created_at and l.created_at.date() == today]
    if todays:
        return ok(
            data=[LessonOut.model_validate(l).model_dump() for l in todays],
            message="Today's lessons",
        )

    day = len(study_dates) + 1
    cached = await cache_get(cache_key)
    generated = cached or await generate_daily_lessons(
        user.goal or "grow my career", day
    )
    await cache_set(cache_key, generated)

    created = [
        Lesson(
            user_id=user.id,
            day=day,
            title=item.get("title", "Lesson"),
            content=item.get("content"),
        )
        for item in generated
    ]
    session.add_all(created)
    await session.commit()
    # expire_on_commit is False, so ids/values are already populated — no refresh.
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
    return ok(data=LessonOut.model_validate(lesson).model_dump(), message="Lesson completed")
