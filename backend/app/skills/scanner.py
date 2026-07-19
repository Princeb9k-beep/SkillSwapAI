"""
AI Skill Scanner (spec §3.9) — extract skills + gaps from pasted text.

Given résumé / portfolio / GitHub / LinkedIn text (pasted, not file-parsed here)
and the user's goal, Groq returns strengths (skills they clearly have), missing
skills to reach the goal, and concrete next steps. Stateless; degrades gracefully.
"""

from __future__ import annotations

from ..groq_client import generate_json

_MAX_CHARS = 6000  # bound tokens

_FALLBACK = {
    "summary": "AI analysis is unavailable (configure GROQ_API_KEY).",
    "strengths": [],
    "missing": [],
    "next_steps": ["Set GROQ_API_KEY on the server to enable skill scanning."],
}


async def analyze(text: str, goal: str | None) -> dict:
    """Return {summary, strengths[], missing[], next_steps[]}."""
    snippet = text.strip()[:_MAX_CHARS]
    prompt = (
        "Analyze this professional text (résumé / portfolio / profile) for a learner "
        f"whose goal is: '{goal or 'grow their career'}'.\n"
        "Return JSON with keys: "
        '"summary" (string), '
        '"strengths" (array of concise skill names they clearly have), '
        '"missing" (array of skill names they should learn to reach the goal), '
        '"next_steps" (array of short actionable steps).\n\n'
        f"TEXT:\n```\n{snippet}\n```"
    )
    try:
        data = await generate_json(prompt, max_tokens=900)
        if isinstance(data, dict):
            return {
                "summary": str(data.get("summary", "")),
                "strengths": [str(s) for s in data.get("strengths", [])][:20],
                "missing": [str(s) for s in data.get("missing", [])][:20],
                "next_steps": [str(s) for s in data.get("next_steps", [])][:10],
            }
    except Exception:  # noqa: BLE001 - graceful fallback
        pass
    return _FALLBACK
