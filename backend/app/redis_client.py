"""
Async Redis connection management.

Redis is treated as an *optional* dependency: if it is unavailable the app still
boots and simply skips caching/locking (graceful degradation — a system-design
resilience principle). Callers should tolerate `get_redis()` returning None.
"""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from .config import get_settings

logger = logging.getLogger("skillswap.redis")

_redis: aioredis.Redis | None = None
_initialized = False


async def init_redis() -> aioredis.Redis | None:
    """Create the connection pool and verify connectivity once."""
    global _redis, _initialized
    if _initialized:
        return _redis
    _initialized = True
    settings = get_settings()
    try:
        client = aioredis.from_url(
            settings.redis_url,
            password=settings.redis_password or None,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        await client.ping()
        _redis = client
        logger.info("Connected to Redis")
    except Exception as exc:  # noqa: BLE001 - degrade gracefully
        logger.warning("Redis unavailable, caching/locks disabled: %s", exc)
        _redis = None
    return _redis


def get_redis() -> aioredis.Redis | None:
    """Return the shared client (or None when Redis is unavailable)."""
    return _redis


async def close_redis() -> None:
    global _redis, _initialized
    if _redis is not None:
        await _redis.aclose()
    _redis = None
    _initialized = False
