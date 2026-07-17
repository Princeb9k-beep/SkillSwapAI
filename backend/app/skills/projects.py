"""Project-suggestion skill."""

from __future__ import annotations

from ..groq_client import generate_json


async def suggest_projects(skill: str, level: str, count: int) -> list[dict]:
    """Suggest `count` portfolio projects to practice a skill at a given level."""
    prompt = (
        f"Suggest {count} portfolio projects to practice '{skill}' at {level} level. "
        "Return JSON array of objects: "
        "{\"title\": string, \"description\": string, \"difficulty\": "
        "\"easy\"|\"medium\"|\"hard\"}."
    )
    try:
        data = await generate_json(prompt, max_tokens=900)
        if isinstance(data, list):
            return data[:count]
        if isinstance(data, dict) and "projects" in data:
            return data["projects"][:count]
    except Exception:  # noqa: BLE001
        pass
    return [
        {
            "title": f"Build something with {skill}",
            "description": "A hands-on project. Configure GROQ_API_KEY for tailored ideas.",
            "difficulty": level if level in {"easy", "medium", "hard"} else "medium",
        }
    ]
