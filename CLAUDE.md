# CLAUDE.md — SkillSwap AI

Guidance for working in this repo.

## What this is
A full-stack AI career app: FastAPI + async PostgreSQL + Redis + Groq backend, and a
React (Vite) SPA frontend. Features: roadmap generation, project suggestions, resume
builder, interview practice, daily lessons.

## Architecture (backend)
- `backend/main.py` — app entry: lifespan initializes DB/Redis/Groq, CORS, an AI
  rate-limit middleware, a uniform error-envelope handler, and mounts routers.
- `backend/app/`
  - `config.py` — typed settings (pydantic-settings); `async_database_url` normalizes
    Render's `postgres://` to `postgresql+asyncpg://`.
  - `database.py` / `redis_client.py` — async engine + optional Redis (degrades if down).
  - `models.py` — six tables: users, skills, roadmaps, projects, lessons, interviews.
  - `skills/` — one focused AI task per module (superpowers-style). Routers delegate here.
  - `concurrency.py` — Redis distributed lock (the "ECC-style" pattern).
  - `resilience.py` — retry+backoff, token-bucket rate limiter (system-design-primer).
  - `responses.py` — the `{success, data, message, meta}` envelope (ui-ux-pro-max).
- `backend/alembic/` — async migrations; `0001_initial_schema.py` builds all tables.

## Architecture (frontend)
- `frontend/src/App.jsx` — routes, each page `React.lazy`-loaded inside a `Suspense`.
- `api/client.js` — unwraps the response envelope; sends `X-User-Id` (stubbed auth).
- `components/States.jsx` — shared loading/error/empty states.

## Conventions
- Every endpoint returns the standard envelope via `app/responses.py`.
- AI calls go through `app/groq_client.py` (retries + Redis cache); never call Groq directly.
- New AI features = new module in `app/skills/` + a thin router in `app/routers/`.
- Keep Redis/Groq optional: features must degrade gracefully when they're unavailable.

## Verify
```bash
cd backend && pip install -r requirements.txt && pytest -q        # offline smoke tests
cd backend && alembic upgrade head && alembic downgrade base      # migrations (needs DATABASE_URL)
cd frontend && npm install && npm run build                        # frontend build
```

## Vendored skills
`claude_skills/` holds the skill definitions (not full repos) from the four source
repos. `claude_skills/INTEGRATION.md` maps each borrowed pattern to the file that
implements it.
