"""
Redis caching helpers.

Thin JSON cache used for AI responses, roadmaps, and daily-lesson progress. Keys are
namespaced and values are JSON-encoded. All operations degrade to no-ops when Redis
is unavailable so the app keeps working (just slower / recomputing).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from .config import get_settings
from .redis_client import get_redis

logger = logging.getLogger("skillswap.cache")


def make_key(*parts: Any) -> str:
    """Build a stable cache key from arbitrary parts (hashing long/complex ones)."""
    raw = ":".join(str(p) for p in parts)
    if len(raw) > 200:
        digest = hashlib.sha256(raw.encode()).hexdigest()[:32]
        return f"{parts[0]}:{digest}"
    return raw


async def cache_get(key: str) -> Any | None:
    redis = get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache_get failed for %s: %s", key, exc)
        return None


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    redis = get_redis()
    if redis is None:
        return
    ttl = ttl if ttl is not None else get_settings().ai_cache_ttl_seconds
    try:
        await redis.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache_set failed for %s: %s", key, exc)
