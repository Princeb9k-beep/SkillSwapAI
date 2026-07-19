"""
Live translation (spec §3.3) — text translation via Groq.

Translates chat/notes into a target language so partners who speak different
languages can learn together. Cached per (text, language); degrades gracefully to
the original text when Groq is unavailable. (Voice/video captioning needs an audio
pipeline and is out of scope here — this is the text path.)
"""

from __future__ import annotations

from ..cache import cache_get, cache_set, make_key
from ..groq_client import generate

# A friendly allowlist for the UI; any language name also works.
LANGUAGES = [
    "Spanish", "French", "German", "Italian", "Portuguese", "Dutch",
    "Chinese", "Japanese", "Korean", "Arabic", "Hindi", "Russian", "English",
]


async def translate(text: str, target_language: str) -> dict:
    """Return {translation, target_language}. Falls back to the original text."""
    snippet = text.strip()[:4000]
    cache_key = make_key("translate", target_language, snippet)
    cached = await cache_get(cache_key)
    if cached is not None:
        return {"translation": cached, "target_language": target_language}

    prompt = (
        f"Translate the following text into {target_language}. "
        "Return ONLY the translation, no quotes or notes.\n\n"
        f"{snippet}"
    )
    try:
        result = (await generate(prompt, max_tokens=1000, temperature=0.2, cache=False)).strip()
        if result:
            await cache_set(cache_key, result)
            return {"translation": result, "target_language": target_language}
    except Exception:  # noqa: BLE001 - graceful fallback
        pass
    return {
        "translation": text,
        "target_language": target_language,
        "note": "Translation unavailable (configure GROQ_API_KEY).",
    }
