"""AI-suggested opening messages for a matched partner.

Generates a few short, friendly first-message ideas grounded in what the partner
can teach and what the user wants to learn. Falls back to sensible templates when
Groq isn't configured.
"""

from __future__ import annotations

from ..groq_client import generate_json

COUNT = 3


def _fallback(partner_name: str, their_skills: list[str], my_wants: list[str]) -> list[str]:
    teach = their_skills[0] if their_skills else "your skills"
    learn = my_wants[0] if my_wants else "something new"
    name = partner_name or "there"
    return [
        f"Hi {name}! I'd love to learn {teach} from you — what got you into it?",
        f"Hey {name}, I'm working toward {learn}. Would you be up for a skill swap?",
        f"Hi {name}! Your {teach} experience caught my eye. Free for a quick intro chat?",
    ]


async def generate_icebreakers(
    partner_name: str, their_skills: list[str], my_wants: list[str]
) -> list[str]:
    teach = ", ".join(their_skills[:5]) or "various skills"
    learn = ", ".join(my_wants[:5]) or "new skills"
    prompt = (
        f"Write {COUNT} short, warm, specific first-message openers to start a "
        f"skill-swap conversation with {partner_name or 'a learning partner'}. "
        f"They can teach: {teach}. I want to learn: {learn}. Each opener is one "
        "sentence, friendly, no emojis required. Return a JSON array of strings."
    )
    try:
        data = await generate_json(prompt, max_tokens=400, temperature=0.7)
        items = data if isinstance(data, list) else data.get("openers", []) if isinstance(data, dict) else []
        cleaned = [str(x).strip() for x in items if str(x).strip()]
        if len(cleaned) >= 2:
            return cleaned[:COUNT]
    except Exception:  # noqa: BLE001
        pass
    return _fallback(partner_name, their_skills, my_wants)
