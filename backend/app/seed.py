"""Starter content so the app doesn't feel empty on day one.

A brand-new install (or a brand-new user) lands on a Community tab with nothing in
it, which reads as "this app is dead". We fix the *honest* part of that emptiness by
seeding a handful of official, platform-owned communities (``created_by=None`` — they
belong to no user, so nothing here pretends to be another member). User-dependent
sections (Matches, Feed, Messages) are left to their improved empty states instead of
fake data, which would be deceptive.

Seeding is idempotent: it keys on ``name_normalized`` and inserts only what's missing,
so it's safe to run on every startup.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Community

logger = logging.getLogger("skillswap")

# Official communities every user can join from the start. Kept small and broad so
# they stay relevant, and named so they won't collide with what users create.
OFFICIAL_COMMUNITIES: list[dict[str, str]] = [
    {
        "name": "Welcome to SkillSwap",
        "topic": "General",
        "description": "New here? Introduce yourself, ask anything, and find your first swap partner.",
    },
    {
        "name": "Coding & Web Dev",
        "topic": "Coding",
        "description": "Python, JavaScript, web, and everything software. Share wins, ask for reviews.",
    },
    {
        "name": "Design & Creativity",
        "topic": "Design",
        "description": "UI/UX, illustration, photography, and design feedback for makers of all levels.",
    },
    {
        "name": "Languages",
        "topic": "Languages",
        "description": "Practice a new language with a partner — from your first words to fluency.",
    },
    {
        "name": "Music & Instruments",
        "topic": "Music",
        "description": "Guitar, piano, production, and more. Swap lessons and share what you're learning.",
    },
    {
        "name": "Career & Interview Prep",
        "topic": "Career",
        "description": "Resumes, portfolios, and mock interviews. Level up your job search together.",
    },
]


async def seed_starter_content(session: AsyncSession) -> int:
    """Insert any missing official communities. Returns how many were created.

    Idempotent and safe to call on every boot. Never raises into startup — a seeding
    hiccup should not stop the app from serving.
    """
    try:
        existing = {
            row[0]
            for row in (
                await session.execute(select(Community.name_normalized))
            ).all()
        }
        created = 0
        for spec in OFFICIAL_COMMUNITIES:
            normalized = spec["name"].strip().lower()
            if normalized in existing:
                continue
            session.add(
                Community(
                    name=spec["name"],
                    name_normalized=normalized,
                    topic=spec["topic"],
                    description=spec["description"],
                    created_by=None,  # platform-owned, not attributed to any user
                )
            )
            created += 1
        if created:
            await session.commit()
            logger.info("Seeded %d official communities", created)
        return created
    except Exception:  # pragma: no cover - defensive; never break startup
        logger.exception("Starter-content seeding failed (continuing without it)")
        await session.rollback()
        return 0
