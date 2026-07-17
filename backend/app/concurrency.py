"""
ECC-style concurrency control (Redis distributed lock).

`affaan-m/ECC` is a Claude Code agent-harness project, not a Python locking library,
so the "ECC-style concurrency control" requested in the brief is implemented here as
the well-known safe Redis lock pattern:

  * Acquire with SET key value NX PX <ttl>   (atomic create-if-absent + expiry)
  * Release with a Lua compare-and-delete    (only the owner may unlock)
  * A bounded acquire loop with exponential backoff (system-design-primer retry idea)

Used to make AI generation idempotent per (user, task): if two requests race, only
one does the expensive Groq call while the other waits and reads the cached result.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator

from .config import get_settings
from .redis_client import get_redis

# Atomic "delete only if I still own it" — prevents releasing someone else's lock
# that has since expired and been re-acquired.
_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


async def acquire_lock(
    key: str,
    *,
    ttl_ms: int | None = None,
    max_wait_ms: int = 10_000,
    base_delay_ms: int = 50,
) -> str | None:
    """
    Try to acquire ``lock:{key}``. Returns an opaque owner token on success, or
    None if Redis is down (callers should proceed without the lock) or the lock
    could not be obtained within ``max_wait_ms``.
    """
    redis = get_redis()
    if redis is None:
        return None  # degrade: no lock available, let the caller proceed

    settings = get_settings()
    ttl = ttl_ms or settings.lock_ttl_ms
    token = uuid.uuid4().hex
    lock_key = f"lock:{key}"

    waited = 0
    delay = base_delay_ms
    while True:
        if await redis.set(lock_key, token, nx=True, px=ttl):
            return token
        if waited >= max_wait_ms:
            return None
        await asyncio.sleep(delay / 1000)
        waited += delay
        delay = min(delay * 2, 1000)  # exponential backoff, capped at 1s


async def release_lock(key: str, token: str | None) -> None:
    """Release the lock iff we still own it. No-op when token is None."""
    if token is None:
        return
    redis = get_redis()
    if redis is None:
        return
    with contextlib.suppress(Exception):
        await redis.eval(_RELEASE_SCRIPT, 1, f"lock:{key}", token)


@contextlib.asynccontextmanager
async def distributed_lock(key: str, **kwargs) -> AsyncIterator[bool]:
    """
    Async context manager wrapper.

    Yields True when the lock was held, False when it was skipped (Redis down) or
    could not be acquired. Callers decide how to behave in the False case
    (typically: proceed anyway, or re-check the cache).
    """
    token = await acquire_lock(key, **kwargs)
    try:
        yield token is not None
    finally:
        await release_lock(key, token)
