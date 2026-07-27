"""Generate flashcards (front/back Q&A pairs) for a topic via AI.

Falls back to a couple of generic prompt cards when Groq isn't configured, so the
flow always produces something reviewable.
"""

from __future__ import annotations

from ..groq_client import generate_json

MAX_CARDS = 6


def _sanitize(raw: list) -> list[dict]:
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        front = str(item.get("front") or item.get("question") or "").strip()
        back = str(item.get("back") or item.get("answer") or "").strip()
        if front and back:
            out.append({"front": front[:500], "back": back[:1000]})
    return out


def _fallback(topic: str) -> list[dict]:
    return [
        {"front": f"What is the core idea of {topic}?", "back": f"Write, in your own words, the one-sentence essence of {topic}."},
        {"front": f"Name a practical use of {topic}.", "back": f"Recall a real situation where {topic} applies."},
        {"front": f"What's one common mistake with {topic}?", "back": f"Think of a pitfall beginners hit with {topic}."},
    ]


async def generate_cards(topic: str, source_text: str | None = None) -> list[dict]:
    context = f"\n\nBase them on this material:\n{source_text[:4000]}" if source_text else ""
    prompt = (
        f"Create up to {MAX_CARDS} study flashcards for the topic '{topic}'. Each "
        "card has a concise question ('front') and a correct, self-contained answer "
        "('back'). Return ONLY a JSON array of {\"front\": string, \"back\": string}."
        f"{context}"
    )
    try:
        data = await generate_json(prompt, max_tokens=1200, temperature=0.5)
        items = data if isinstance(data, list) else data.get("cards", []) if isinstance(data, dict) else []
        cleaned = _sanitize(items)
        if cleaned:
            return cleaned[:MAX_CARDS]
    except Exception:  # noqa: BLE001
        pass
    return _fallback(topic)
