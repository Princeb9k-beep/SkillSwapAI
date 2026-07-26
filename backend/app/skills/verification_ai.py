"""AI skill-assessment quiz generation.

Produces a small multiple-choice quiz for a skill. Falls back to a generic
self-assessment quiz when Groq isn't configured, so the flow always works
(the fallback is intentionally easy — real gating needs GROQ_API_KEY).
"""

from __future__ import annotations

from ..groq_client import generate_json

QUESTION_COUNT = 5


def _sanitize(raw: list) -> list[dict]:
    """Keep only well-formed {question, options[2-6], answer index} items."""
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        q = str(item.get("question", "")).strip()
        options = item.get("options")
        answer = item.get("answer")
        if not q or not isinstance(options, list) or len(options) < 2:
            continue
        options = [str(o) for o in options][:6]
        try:
            answer = int(answer)
        except (TypeError, ValueError):
            continue
        if not 0 <= answer < len(options):
            continue
        out.append({"question": q, "options": options, "answer": answer})
    return out


def _fallback_quiz(skill: str) -> list[dict]:
    return [
        {
            "question": f"How would you rate your hands-on experience with {skill}?",
            "options": [
                "I've never used it",
                "A little, guided by tutorials",
                "I use it comfortably on real work",
                "I could teach it to others",
            ],
            "answer": 3,
        },
        {
            "question": f"Have you shipped something real using {skill}?",
            "options": ["No", "A practice project", "Yes, more than one"],
            "answer": 2,
        },
        {
            "question": f"Could you debug a tricky {skill} problem without help?",
            "options": ["Not yet", "Sometimes", "Usually yes"],
            "answer": 2,
        },
        {
            "question": f"Do you understand the core concepts behind {skill}?",
            "options": ["Still learning", "Mostly", "Deeply"],
            "answer": 2,
        },
        {
            "question": f"Would peers consider you a go-to person for {skill}?",
            "options": ["No", "Maybe", "Yes"],
            "answer": 2,
        },
    ]


async def generate_quiz(skill: str) -> list[dict]:
    prompt = (
        f"Create a {QUESTION_COUNT}-question multiple-choice quiz that tests real "
        f"competence in the skill '{skill}'. Each question must have exactly 4 "
        "plausible options and one correct option. Return ONLY a JSON array of "
        '{"question": string, "options": [4 strings], "answer": index 0-3}.'
    )
    try:
        data = await generate_json(prompt, max_tokens=1000, temperature=0.5)
        items = data if isinstance(data, list) else data.get("questions", []) if isinstance(data, dict) else []
        cleaned = _sanitize(items)
        if len(cleaned) >= 3:
            return cleaned[:QUESTION_COUNT]
    except Exception:  # noqa: BLE001
        pass
    return _fallback_quiz(skill)
