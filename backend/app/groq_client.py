"""
Groq AI client wrapper.

All AI work funnels through `generate()`, which composes the patterns from the
vendored skills:

  * resilience.retry_with_backoff  — tolerate transient Groq/network errors
  * cache (Redis)                  — memoize identical prompts (ai_cache_ttl)
  * graceful degradation           — if GROQ_API_KEY is missing the app still boots
    and returns a clear, enveloped error instead of crashing.

`generate_json()` additionally coerces the model into returning strict JSON, which
the skill task modules parse into structured roadmap/interview payloads.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from groq import AsyncGroq

from .cache import cache_get, cache_set, make_key
from .config import get_settings
from .resilience import retry_with_backoff

logger = logging.getLogger("skillswap.groq")

_client: AsyncGroq | None = None


class AIUnavailableError(RuntimeError):
    """Raised when the AI backend can't fulfil a request (e.g. no API key)."""


def init_groq() -> AsyncGroq | None:
    """Create the Groq client once. Returns None if no key is configured."""
    global _client
    settings = get_settings()
    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY not set — AI endpoints will return an error.")
        _client = None
        return None
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key)
    return _client


def get_groq() -> AsyncGroq | None:
    return _client


async def generate(
    prompt: str,
    *,
    system: str = "You are SkillSwap AI, an expert career and learning coach.",
    temperature: float = 0.7,
    max_tokens: int = 1200,
    cache: bool = True,
) -> str:
    """
    Run a single chat completion and return the text, with retries + Redis caching.
    """
    settings = get_settings()
    cache_key = make_key("ai", settings.groq_model, system, prompt) if cache else None

    if cache_key:
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

    client = get_groq()
    if client is None:
        raise AIUnavailableError(
            "AI is not configured on the server (missing GROQ_API_KEY)."
        )

    async def _call() -> str:
        completion = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content or ""

    text = await retry_with_backoff(_call, retries=3, base_delay=0.5)

    if cache_key:
        await cache_set(cache_key, text)
    return text


async def generate_json(
    prompt: str,
    *,
    system: str = "You are SkillSwap AI. Respond ONLY with valid JSON, no prose.",
    **kwargs: Any,
) -> Any:
    """Generate and parse a JSON payload, tolerating markdown code fences."""
    raw = await generate(prompt, system=system, **kwargs)
    return _parse_json(raw)


def _parse_json(raw: str) -> Any:
    """Best-effort JSON extraction from an LLM response."""
    text = raw.strip()
    if text.startswith("```"):
        # strip ```json ... ``` fences
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # last resort: grab the outermost {...} or [...]
        for open_c, close_c in (("{", "}"), ("[", "]")):
            start, end = text.find(open_c), text.rfind(close_c)
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    continue
        raise
