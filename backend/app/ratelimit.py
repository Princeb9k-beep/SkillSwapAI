"""HTTP rate-limiting dependencies.

Thin FastAPI wrappers over the Redis-backed TokenBucketRateLimiter. Keyed by
client IP so abusive callers are throttled without affecting others. Fails open
when Redis is down (see resilience.py), so local dev and tests are unaffected.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from .resilience import TokenBucketRateLimiter


def _client_ip(request: Request) -> str:
    # Honor the first proxy hop (Render sits behind a proxy), else the socket peer.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(name: str, limit: int, window_seconds: int):
    """Dependency factory: allow `limit` requests per `window_seconds` per IP for
    the route group `name`, else 429."""
    limiter = TokenBucketRateLimiter(limit=limit, window_seconds=window_seconds)

    async def dep(request: Request) -> None:
        key = f"{name}:{_client_ip(request)}"
        if not await limiter.allow(key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait a moment and try again.",
            )

    return dep
