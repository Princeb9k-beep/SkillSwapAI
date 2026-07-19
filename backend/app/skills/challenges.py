"""
Daily AI Challenges (spec §3.8) — a bite-sized, Groq-generated challenge per day,
personalized to the user's goal. Completing one awards XP + streak (gamification).
Degrades gracefully to a templated challenge when Groq is unavailable.
"""

from __future__ import annotations

from ..cache import cache_get, cache_set, make_key
from ..groq_client import generate_json

_FALLBACK = {
    "title": "Practice for 15 minutes",
    "description": "Spend 15 focused minutes on your goal today. "
    "(Configure GROQ_API_KEY for a fresh AI-generated challenge each day.)",
}


async def generate_challenge(goal: str, day_ordinal: int) -> dict:
    """Generate today's challenge (cached per user/day by the caller's key)."""
    cache_key = make_key("challenge", goal, day_ordinal)
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    prompt = (
        f"Create ONE fun, bite-sized daily challenge (doable in ~15 minutes) for "
        f"someone whose goal is: '{goal}'. Examples of the vibe: 'Learn one Spanish "
        f"phrase', 'Solve a small coding problem', 'Sketch a logo'. "
        'Return JSON: {"title": string, "description": string}.'
    )
    try:
        data = await generate_json(prompt, max_tokens=300)
        if isinstance(data, dict) and data.get("title"):
            result = {
                "title": str(data["title"]),
                "description": str(data.get("description", "")),
            }
            await cache_set(cache_key, result)
            return result
    except Exception:  # noqa: BLE001 - graceful fallback
        pass
    return _FALLBACK
