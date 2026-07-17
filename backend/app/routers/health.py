"""Health/readiness endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ..database import get_engine
from ..groq_client import get_groq
from ..redis_client import get_redis
from ..responses import ok

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> object:
    """Report liveness plus the status of each backing service."""
    services = {"database": "unknown", "redis": "down", "groq": "unconfigured"}

    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        services["database"] = "up"
    except Exception:  # noqa: BLE001
        services["database"] = "down"

    redis = get_redis()
    if redis is not None:
        try:
            await redis.ping()
            services["redis"] = "up"
        except Exception:  # noqa: BLE001
            services["redis"] = "down"

    if get_groq() is not None:
        services["groq"] = "configured"

    return ok(data={"status": "ok", "services": services}, message="SkillSwap AI is running")
