"""Skill Academy: a catalog of paid, AI-guided skill courses (spec extension).

Browse the catalog, enroll (purchase) in a path, work through step-by-step
modules with hands-on exercises and integrated tools, mark lessons complete
(earning XP), and get AI tutoring on any lesson. The catalog is code-defined
(skills/catalog.py); enrollment + progress are persisted.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import SkillEnrollment, SkillProgress, User
from ..responses import error, ok
from ..schemas import LessonAssistRequest
from ..skills import catalog
from ..skills.academy_ai import lesson_article, lesson_assist
from ..skills.gamification import record_activity

router = APIRouter(prefix="/academy", tags=["academy"])

# How many lessons are readable before enrolling (a free preview).
PREVIEW_LESSONS = 1
XP_PER_LESSON = 15


def _path_card(path: dict, enrolled: bool, done: int) -> dict:
    total = path["lesson_count"]
    return {
        "slug": path["slug"],
        "title": path["title"],
        "category": path["category"],
        "difficulty": path["difficulty"],
        "price_cents": path["price_cents"],
        "hours": path["hours"],
        "summary": path["summary"],
        "lesson_count": total,
        "module_count": len(path["modules"]),
        "tools": path["tools"],
        "enrolled": enrolled,
        "completed": done,
        "progress": round(100 * done / total) if total else 0,
    }


async def _enrolled_slugs(session: AsyncSession, user_id: int) -> set[str]:
    rows = await session.execute(
        select(SkillEnrollment.path_slug).where(SkillEnrollment.user_id == user_id)
    )
    return {r[0] for r in rows.all()}


async def _completed_keys(session: AsyncSession, user_id: int, slug: str) -> set[str]:
    rows = await session.execute(
        select(SkillProgress.lesson_key).where(
            SkillProgress.user_id == user_id, SkillProgress.path_slug == slug
        )
    )
    return {r[0] for r in rows.all()}


@router.get("/categories")
async def list_categories(user: User = Depends(get_current_user)) -> object:
    return ok(data=["All", *catalog.categories()])


@router.get("/paths")
async def list_paths(
    category: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """The catalog (optionally filtered by category), with my enrollment/progress."""
    enrolled = await _enrolled_slugs(session, user.id)
    # Per-path completion counts in one query.
    counts: dict[str, int] = {}
    rows = await session.execute(
        select(SkillProgress.path_slug).where(SkillProgress.user_id == user.id)
    )
    for (slug,) in rows.all():
        counts[slug] = counts.get(slug, 0) + 1

    data = [
        _path_card(p, p["slug"] in enrolled, counts.get(p["slug"], 0))
        for p in catalog.list_paths(category)
    ]
    return ok(data=data, meta={"total": len(catalog.CATALOG)})


@router.get("/paths/{slug}")
async def get_path(
    slug: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Full path detail. Lesson bodies are unlocked once enrolled; before that,
    only a short preview is readable (the rest is marked locked)."""
    path = catalog.get_path(slug)
    if path is None:
        return error("Skill not found.", status_code=404, code="not_found")

    enrolled = slug in await _enrolled_slugs(session, user.id)
    done = await _completed_keys(session, user.id, slug)

    seen = 0
    modules = []
    for module in path["modules"]:
        lessons = []
        for lesson in module["lessons"]:
            unlocked = enrolled or seen < PREVIEW_LESSONS
            seen += 1
            entry = {
                "key": lesson["key"],
                "title": lesson["title"],
                "summary": lesson["summary"],
                "completed": lesson["key"] in done,
                "locked": not unlocked,
            }
            if unlocked:
                entry["steps"] = lesson["steps"]
                entry["exercise"] = lesson["exercise"]
                entry["tools"] = lesson["tools"]
            lessons.append(entry)
        modules.append({"title": module["title"], "lessons": lessons})

    return ok(
        data={
            **_path_card(path, enrolled, len(done)),
            "modules": modules,
        }
    )


@router.post("/paths/{slug}/enroll")
async def enroll(
    slug: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Enroll in (purchase) a skill path. Payment is stubbed like the rest of the
    marketplace — enrolling grants full access to the course."""
    path = catalog.get_path(slug)
    if path is None:
        return error("Skill not found.", status_code=404, code="not_found")
    exists = (
        await session.execute(
            select(SkillEnrollment).where(
                SkillEnrollment.user_id == user.id, SkillEnrollment.path_slug == slug
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(SkillEnrollment(user_id=user.id, path_slug=slug))
        await session.commit()
    return ok(message=f"Enrolled in {path['title']}", status_code=201)


@router.get("/paths/{slug}/lessons/{key}/content")
async def lesson_content(
    slug: str,
    key: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """The taught lesson: an AI-written article plus curated video + reading
    resources. Requires enrollment (beyond the free preview lesson)."""
    found = catalog.get_lesson(slug, key)
    if found is None:
        return error("Lesson not found.", status_code=404, code="not_found")
    path, lesson = found

    enrolled = slug in await _enrolled_slugs(session, user.id)
    is_preview = key in catalog.all_lesson_keys(slug)[:PREVIEW_LESSONS]
    if not enrolled and not is_preview:
        return error("Enroll to open this lesson.", status_code=403, code="not_enrolled")

    article = await lesson_article(path, lesson)
    return ok(
        data={
            "title": lesson["title"],
            "summary": lesson["summary"],
            "steps": lesson["steps"],
            "exercise": lesson["exercise"],
            "tools": lesson["tools"],
            "resources": catalog.lesson_resources(path, lesson),
            **article,
        }
    )


@router.post("/paths/{slug}/lessons/{key}/complete")
async def complete_lesson(
    slug: str,
    key: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Mark a lesson complete (must be enrolled). Awards XP the first time."""
    found = catalog.get_lesson(slug, key)
    if found is None:
        return error("Lesson not found.", status_code=404, code="not_found")
    enrolled = (
        await session.execute(
            select(SkillEnrollment).where(
                SkillEnrollment.user_id == user.id, SkillEnrollment.path_slug == slug
            )
        )
    ).scalar_one_or_none()
    if enrolled is None:
        return error("Enroll to track your progress.", status_code=403, code="not_enrolled")

    already = (
        await session.execute(
            select(SkillProgress).where(
                SkillProgress.user_id == user.id,
                SkillProgress.path_slug == slug,
                SkillProgress.lesson_key == key,
            )
        )
    ).scalar_one_or_none()
    new_achievements: list = []
    if already is None:
        session.add(SkillProgress(user_id=user.id, path_slug=slug, lesson_key=key))
        new_achievements = await record_activity(session, user, xp=XP_PER_LESSON)
        await session.commit()

    done = await _completed_keys(session, user.id, slug)
    total = len(catalog.all_lesson_keys(slug))
    return ok(
        data={
            "completed": len(done),
            "total": total,
            "progress": round(100 * len(done) / total) if total else 0,
            "xp": user.xp,
            "new_achievements": [a.title for a in new_achievements],
        },
        message="Lesson complete",
    )


@router.post("/paths/{slug}/lessons/{key}/assist")
async def assist(
    slug: str,
    key: str,
    payload: LessonAssistRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """AI tutor for a lesson: explain the concept, hint at the exercise, or
    review submitted work. Requires enrollment (beyond the preview lesson)."""
    found = catalog.get_lesson(slug, key)
    if found is None:
        return error("Lesson not found.", status_code=404, code="not_found")
    path, lesson = found

    enrolled = slug in await _enrolled_slugs(session, user.id)
    is_preview = key in catalog.all_lesson_keys(slug)[:PREVIEW_LESSONS]
    if not enrolled and not is_preview:
        return error("Enroll to use the AI tutor for this lesson.", status_code=403, code="not_enrolled")

    result = await lesson_assist(path, lesson, payload.mode, payload.question)
    return ok(data=result)
