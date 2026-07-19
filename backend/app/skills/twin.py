"""
AI Twin (spec §4) — the differentiator. Learns how a user teaches, then mimics that
style so partners can keep learning from them 24/7.

- distill_style(): condense a user's teaching samples into a reusable style profile
  (Groq; falls back to the raw samples).
- twin_reply(): answer a learner's question *as* the owner's twin, primed with the
  owner's style profile + the skills they teach, using recent session memory.
- twin_quiz(): generate quiz questions in the owner's style about a topic.

All Groq calls degrade gracefully so the feature never hard-fails.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..groq_client import AIUnavailableError, chat, generate, generate_json
from ..models import Skill, TwinMessage, User

HISTORY_LIMIT = 12


async def distill_style(samples: str) -> str:
    """Condense teaching samples into a concise style profile."""
    prompt = (
        "From the following samples of how a person teaches/explains, write a short "
        "'teaching style profile' (3-5 sentences) capturing their tone, structure, and "
        "habits, so another AI can imitate how they teach.\n\n"
        f"SAMPLES:\n{samples[:6000]}"
    )
    try:
        return (await generate(prompt, max_tokens=300, temperature=0.4)).strip()
    except Exception:  # noqa: BLE001
        # Fallback: keep the raw samples as the style seed.
        return samples.strip()[:2000]


async def _owner_skills(session: AsyncSession, owner_id: int) -> str:
    rows = await session.execute(
        select(Skill.name).where(Skill.user_id == owner_id, Skill.kind == "have")
    )
    names = [r[0] for r in rows.all()]
    return ", ".join(names) if names else "general topics"


def _system_prompt(owner_name: str, style: str, skills: str) -> str:
    return (
        f"You are {owner_name}'s AI Twin — you teach in {owner_name}'s voice and style, "
        f"as a patient 1-on-1 mentor. Teach the topics {owner_name} knows: {skills}.\n"
        f"Their teaching style: {style or 'clear, encouraging, example-driven'}.\n"
        "Stay in character, be concise, and always give a concrete next step."
    )


async def twin_reply(
    session: AsyncSession, owner: User, style: str, learner: User, message: str
) -> str:
    """Reply to a learner as the owner's twin (persists both turns)."""
    session.add(
        TwinMessage(twin_owner_id=owner.id, learner_id=learner.id, role="user", content=message)
    )
    await session.flush()
    rows = await session.execute(
        select(TwinMessage)
        .where(
            TwinMessage.twin_owner_id == owner.id,
            TwinMessage.learner_id == learner.id,
        )
        .order_by(TwinMessage.id.desc())
        .limit(HISTORY_LIMIT)
    )
    turns = [
        {"role": m.role, "content": m.content} for m in reversed(rows.scalars().all())
    ]
    skills = await _owner_skills(session, owner.id)
    system = _system_prompt(owner.name or f"Learner #{owner.id}", style, skills)

    try:
        reply = await chat(turns, system=system)
    except AIUnavailableError:
        reply = (
            f"This is {owner.name or 'your partner'}'s AI Twin. The AI backend isn't "
            "configured yet (set GROQ_API_KEY) — once it is, I'll answer in their "
            "teaching style."
        )
    except Exception:  # noqa: BLE001
        reply = "Sorry, I hit a snag. Please try again."

    session.add(
        TwinMessage(twin_owner_id=owner.id, learner_id=learner.id, role="assistant", content=reply)
    )
    return reply


async def twin_quiz(owner_name: str, style: str, skills: str, topic: str) -> list[dict]:
    """Generate quiz questions in the owner's style about a topic."""
    prompt = (
        f"As {owner_name}'s AI Twin (teaching style: {style or 'clear and encouraging'}), "
        f"create 3 short quiz questions to test a learner on '{topic}'. "
        'Return JSON array of {"question": string, "answer": string}.'
    )
    try:
        data = await generate_json(prompt, max_tokens=700)
        if isinstance(data, list):
            return [
                {"question": str(q.get("question", "")), "answer": str(q.get("answer", ""))}
                for q in data
                if isinstance(q, dict)
            ][:5]
        if isinstance(data, dict) and "questions" in data:
            return data["questions"][:5]
    except Exception:  # noqa: BLE001
        pass
    return [
        {
            "question": f"What's one key idea about {topic}?",
            "answer": "Set GROQ_API_KEY to get AI-generated quizzes in the twin's style.",
        }
    ]
