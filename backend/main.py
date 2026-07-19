"""
SkillSwap AI — FastAPI application entry point.

Run locally:
    uvicorn main:app --reload
Run on Render:
    uvicorn main:app --host 0.0.0.0 --port $PORT

This module wires everything together:
  * lifespan startup/shutdown initializes the async DB engine, Redis pool, and Groq
    client, and closes them cleanly (system-design-primer: manage resources explicitly).
  * a global exception handler returns the standard UX/UI Pro Max response envelope so
    the frontend renders errors consistently.
  * a lightweight rate limiter protects the AI endpoints and the upstream Groq quota.
  * all feature routers (roadmap, projects, resume, interview, lessons) are mounted.
"""

from __future__ import annotations

import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status

# Serve the PWA manifest with the correct content type.
mimetypes.add_type("application/manifest+json", ".webmanifest")
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import dispose_engine, get_engine
from app.groq_client import init_groq
from app.redis_client import close_redis, init_redis
from app.resilience import TokenBucketRateLimiter
from app.responses import error, ok
from app.routers import (
    auth,
    challenges,
    coach,
    communities,
    health,
    interview,
    lessons,
    marketplace,
    matches,
    portfolio,
    progress,
    projects,
    reputation,
    resume,
    roadmap,
    scanner,
    twin,
    skills,
    users,
    verification,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("skillswap")

# Protect AI-heavy endpoints: 30 requests/minute per user (fails open if Redis down).
# Match the exact API paths (not prefixes) so SPA page routes that share a name —
# /interview, /resume, /lessons — are never rate-limited on navigation.
ai_rate_limiter = TokenBucketRateLimiter(limit=30, window_seconds=60)
_AI_PATHS = frozenset({
    "/roadmap",
    "/projects/suggest",
    "/resume/build",
    "/interview/start",
    "/interview/answer",
    "/lessons/daily",
    "/coach/chat",
    "/scanner/analyze",
    "/challenges/today",
})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down backing services around the app's lifetime."""
    settings = get_settings()
    logger.info("Starting SkillSwap AI (env=%s)", settings.app_env)
    get_engine()            # create the async DB engine
    await init_redis()      # connect Redis (degrades gracefully if unavailable)
    init_groq()             # create Groq client if a key is configured
    try:
        yield
    finally:
        await close_redis()
        await dispose_engine()
        logger.info("SkillSwap AI shut down cleanly")


app = FastAPI(
    title="SkillSwap AI",
    version="1.0.0",
    description=(
        "Duolingo-style gamified learning + ChatGPT-style guidance + LinkedIn "
        "Learning-style career progression, powered by Groq."
    ),
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_ai(request: Request, call_next):
    """Apply the AI rate limiter to expensive endpoints, keyed by X-User-Id/IP."""
    if request.url.path in _AI_PATHS:
        who = request.headers.get("X-User-Id") or (request.client.host if request.client else "anon")
        if not await ai_rate_limiter.allow(f"ai:{who}"):
            return error(
                "You're going a bit fast — please wait a moment and try again.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code="rate_limited",
            )
    return await call_next(request)


# --- Uniform error envelope (UX/UI Pro Max consistency) -------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return error(str(exc.detail), status_code=exc.status_code, code="http_error")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return error(
        "Some fields were invalid. Please check your input.",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="validation_error",
        details=exc.errors(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return error(
        "Something went wrong on our end. Please try again.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_error",
    )


# --- API routes -----------------------------------------------------------
# Registered BEFORE the SPA catch-all below so they always take precedence.
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(skills.router)
app.include_router(matches.router)
app.include_router(progress.router)
app.include_router(communities.router)
app.include_router(verification.router)
app.include_router(portfolio.router)
app.include_router(reputation.router)
app.include_router(marketplace.router)
app.include_router(coach.router)
app.include_router(scanner.router)
app.include_router(challenges.router)
app.include_router(twin.router)
app.include_router(roadmap.router)
app.include_router(projects.router)
app.include_router(resume.router)
app.include_router(interview.router)
app.include_router(lessons.router)


# --- Serve the built React frontend (single-app deployment) ---------------
# One process serves both the API (above) and the SPA. When frontend/dist
# exists (produced by `npm run build`), its assets are mounted and every
# non-API path returns index.html so React Router can handle client-side
# routes (deep links like /dashboard). If dist is absent (API-only dev),
# we fall back to a small JSON welcome at /.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        # Serve real files that exist (serviceWorker.js, icons, etc.);
        # otherwise return index.html for the SPA to route.
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

else:

    @app.get("/")
    async def root() -> object:
        return ok(
            data={"name": "SkillSwap AI", "docs": "/docs", "health": "/health"},
            message="Welcome to SkillSwap AI (frontend not built)",
        )
