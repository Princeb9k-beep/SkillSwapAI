"""
AI Coach (spec §2.4) — a Groq-backed conversational learning coach.

Builds a system prompt from the user's context (goal + skills) so replies are
personalized, sends the recent conversation to Groq, and degrades gracefully to a
helpful canned reply when Groq isn't configured (so the app never hard-fails).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..groq_client import AIUnavailableError, chat
from ..models import CoachMessage, Skill, User

HISTORY_LIMIT = 12  # recent turns sent to the model


async def _system_prompt(session: AsyncSession, user: User) -> str:
    rows = await session.execute(select(Skill).where(Skill.user_id == user.id))
    skills = rows.scalars().all()
    have = ", ".join(s.name for s in skills if s.kind == "have") or "none listed"
    want = ", ".join(s.name for s in skills if s.kind == "want") or "none listed"
    return (
        "You are SkillSwap AI Coach, a supportive, concise learning mentor. Give "
        "practical, encouraging guidance and concrete next steps. Keep answers short "
        "unless asked for depth.\n"
        f"Learner's goal: {user.goal or 'not set'}.\n"
        f"Skills they can teach: {have}.\n"
        f"Skills they want to learn: {want}."
    )


async def coach_reply(session: AsyncSession, user: User, message: str) -> str:
    """Persist the user message, get a reply (or graceful fallback), persist it."""
    session.add(CoachMessage(user_id=user.id, role="user", content=message))

    # Load recent history (including the just-added message via a flush).
    await session.flush()
    rows = await session.execute(
        select(CoachMessage)
        .where(CoachMessage.user_id == user.id)
        .order_by(CoachMessage.id.desc())
        .limit(HISTORY_LIMIT)
    )
    history = list(reversed(rows.scalars().all()))
    turns = [{"role": m.role, "content": m.content} for m in history]

    try:
        system = await _system_prompt(session, user)
        reply = await chat(turns, system=system)
    except AIUnavailableError:
        reply = (
            "I'm your learning coach, but the AI backend isn't configured yet "
            "(set GROQ_API_KEY). Once it's on, ask me anything about your goal, "
            "skills, or a topic you're stuck on."
        )
    except Exception:  # noqa: BLE001 - never hard-fail the endpoint
        reply = "Sorry, I hit a snag answering that. Please try again in a moment."

    session.add(CoachMessage(user_id=user.id, role="assistant", content=reply))
    return reply
