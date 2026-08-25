# syntax=docker/dockerfile:1.7
# SkillSwap AI — single-app image. FastAPI serves the API *and* the built React
# SPA from one process, exactly as the Render deploy does; this just packages it
# so it can run on a box we own with a git-pull deploy in front of it.
#
# Three stages:
#   1. frontend — Vite build → frontend/dist
#   2. builder  — python deps into a venv
#   3. runtime  — slim image, non-root, tini PID1
#
# LAYOUT IS LOAD-BEARING. backend/main.py resolves the SPA as
#   Path(__file__).resolve().parent.parent / "frontend" / "dist"
# so with the app at /app/backend the dist MUST land at /app/frontend/dist. Move
# either one without the other and every browser navigation falls through to the
# JSON welcome route — a 200, so nothing looks broken until you load the page.

######## Stage 1 — frontend (Vite → frontend/dist) ########
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# vite.config.js: build.outDir = "dist" → /build/dist
RUN npm run build

######## Stage 2 — python deps ########
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

######## Stage 3 — runtime ########
FROM python:3.12-slim AS runtime
ARG SOURCE_COMMIT=dev
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    SOURCE_COMMIT=${SOURCE_COMMIT}

# curl is for the HEALTHCHECK below and is not optional — the deploy's health
# gate reads this container's health status, so a missing curl reads as a failed
# deploy and triggers an auto-rollback of a perfectly good build.
RUN apt-get update && apt-get install -y --no-install-recommends tini curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10001 appuser

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser backend/ /app/backend/
COPY --from=frontend --chown=appuser:appuser /build/dist /app/frontend/dist

USER appuser
EXPOSE 8000

# ── HEALTH: ASSERT THE VALUE, NOT THE PRESENCE ───────────────────────────────
# GET /health returns **200 with "database":"down"** when Postgres is
# unreachable (backend/app/routers/health.py builds a services map and always
# answers ok()). A plain `curl -f` would therefore call a database-less
# container healthy, the deploy gate would pass, and the first user request
# would be the thing that discovered it.
#
# responses.ok() returns a JSONResponse, which serialises compact — there is no
# space after the colon, hence the exact literal below. If that ever changes,
# this check fails CLOSED (unhealthy), which is the safe direction.
#
# start-period covers the lifespan: engine create + Redis connect + the
# idempotent starter-content seed.
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health | grep -q '"database":"up"' || exit 1

ENTRYPOINT ["/usr/bin/tini","--"]

# ── WORKERS: 2, AND DELIBERATELY NO --threads ────────────────────────────────
# The allocation is 1 CPU / two lanes. Two lanes means two WORKER PROCESSES.
#
# `--threads` is a NO-OP under UvicornWorker: the flag applies to gthread/sync
# workers only, and an asyncio worker ignores it. Passing `--threads 2` would
# change nothing while making the fleet read as if it had twice the lanes it
# has — a mistake the sibling Nova Flow deployment already made and had to
# audit its way back out of. Concurrency inside a worker comes from the event
# loop (this app's handlers are overwhelmingly `async def`).
#
# --preload: fork after import, so the two workers share the interpreter's
# read-only pages instead of each paying for their own copy — it matters inside
# a 1g limit.
#
# GUNICORN_WORKERS is overridable for one reason: see the note in
# docker-compose.yml about the process-local realtime hub.
CMD ["sh","-c","exec gunicorn --chdir backend main:app \
     --workers ${GUNICORN_WORKERS:-2} \
     --worker-class uvicorn.workers.UvicornWorker \
     --bind 0.0.0.0:8000 --timeout 120 --keep-alive 5 \
     --preload --max-requests 1000 --max-requests-jitter 200"]
