"""Roadmap generation skill."""

from __future__ import annotations

from ..cache import make_key
from ..concurrency import distributed_lock
from ..groq_client import generate_json

_FALLBACK = {
    "summary": "A starter roadmap. Configure GROQ_API_KEY for a personalized plan.",
    "milestones": [
        {
            "title": "Foundations",
            "skills": ["fundamentals"],
            "weeks": 4,
            "steps": ["Learn the basics", "Build a small project"],
        }
    ],
}


async def generate_roadmap(user_id: int, goal: str, current_skills: list[str]) -> dict:
    """
    Produce a structured learning roadmap for a goal. Guarded by a per-user lock so
    concurrent requests don't each trigger a Groq call — the second waits and reads
    the cache inside generate_json.
    """
    skills_str = ", ".join(current_skills) if current_skills else "none stated"
    prompt = (
        f"Create a career learning roadmap for someone whose goal is: '{goal}'.\n"
        f"Their current skills: {skills_str}.\n"
        "Return JSON: {\"summary\": string, \"milestones\": ["
        "{\"title\": string, \"skills\": [string], \"weeks\": number, "
        "\"steps\": [string]}]}. Provide 4-6 milestones ordered from beginner to "
        "job-ready."
    )
    lock_key = make_key("roadmap", user_id)
    async with distributed_lock(lock_key):
        try:
            data = await generate_json(prompt, max_tokens=1600)
            if isinstance(data, dict) and "milestones" in data:
                return data
        except Exception:  # noqa: BLE001 - fall back to a usable default
            pass
    return _FALLBACK
