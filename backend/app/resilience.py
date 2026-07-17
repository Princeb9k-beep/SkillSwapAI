"""
Resilience utilities distilled from `donnemartin/system-design-primer`.

These are the scalability/fault-tolerance primitives the primer recommends for
services that call slower downstreams (like an LLM API):

  * retry_with_backoff  — exponential backoff + jitter around transient failures
  * TokenBucketRateLimiter — Redis-backed rate limiting to protect the app and the
    upstream Groq quota, degrading open when Redis is unavailable.

Each is deliberately small and dependency-free so the design decisions stay legible.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .redis_client import get_redis

logger = logging.getLogger("skillswap.resilience")

T = TypeVar("T")


async def retry_with_backoff(
    func: Callable[[], Awaitable[T]],
    *,
    retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """
    Call ``func`` with exponential backoff + full jitter.

    Backoff = min(max_delay, base_delay * 2**attempt) * random(0, 1). Jitter spreads
    retries so a fleet of clients doesn't synchronize into a thundering herd — a
    core system-design-primer recommendation. Re-raises the last error on exhaustion.
    """
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await func()
        except exceptions as exc:  # noqa: PERF203
            last_exc = exc
            if attempt == retries:
                break
            sleep = min(max_delay, base_delay * (2 ** attempt)) * random.random()
            logger.warning(
                "retry %d/%d after error: %s (sleeping %.2fs)",
                attempt + 1, retries, exc, sleep,
            )
            await asyncio.sleep(sleep)
    assert last_exc is not None
    raise last_exc


class TokenBucketRateLimiter:
    """
    Simple Redis-backed fixed-window rate limiter.

    Allows ``limit`` operations per ``window_seconds`` per key. If Redis is
    unavailable it "fails open" (allows the request) — availability over strict
    enforcement, a conscious trade-off for a learning app.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds

    async def allow(self, key: str) -> bool:
        redis = get_redis()
        if redis is None:
            return True
        bucket = f"ratelimit:{key}:{int(time.time()) // self.window}"
        try:
            current = await redis.incr(bucket)
            if current == 1:
                await redis.expire(bucket, self.window)
            return current <= self.limit
        except Exception as exc:  # noqa: BLE001
            logger.warning("rate limiter degraded (allowing): %s", exc)
            return True
