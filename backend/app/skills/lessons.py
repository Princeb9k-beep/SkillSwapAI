"""Daily lessons skill."""

from __future__ import annotations

from ..groq_client import generate_json


async def generate_daily_lessons(goal: str, day: int, count: int = 3) -> list[dict]:
    """Generate a short set of bite-sized daily lessons toward a goal."""
    prompt = (
        f"Create {count} bite-sized daily micro-lessons (Duolingo style) for day {day} "
        f"of pursuing this goal: '{goal}'. Each should be completable in ~10 minutes. "
        "Return JSON array of {\"title\": string, \"content\": string}."
    )
    try:
        data = await generate_json(prompt, max_tokens=1000)
        if isinstance(data, list):
            return data[:count]
        if isinstance(data, dict) and "lessons" in data:
            return data["lessons"][:count]
    except Exception:  # noqa: BLE001
        pass
    return [
        {
            "title": f"Day {day}: keep going",
            "content": "Spend 10 minutes practicing today. (Configure GROQ_API_KEY "
            "for AI-generated lessons.)",
        }
    ]
