# SkillSwap AI

An AI-powered career-growth app that blends **Duolingo-style gamified learning**,
**ChatGPT-style guidance**, and **LinkedIn Learning-style career progression**.

Tell it a goal ("I want to make $80k") and it generates a personalized **roadmap**,
**daily lessons**, **project suggestions**, a tailored **resume**, and **interview
practice** — powered by **Groq**.

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, async SQLAlchemy 2.0, Alembic |
| AI | Groq (`llama-3.3-70b-versatile` by default) |
| Database | PostgreSQL (async via asyncpg) |
| Cache / locks | Redis (async) |
| Frontend | React 18 + Vite (SPA, lazy-loaded routes, offline service worker) |

Auth is **stubbed** for this version: the client identifies itself with an
`X-User-Id` header (create a user via `POST /users`, then send its id). The `users`
table and password-hash scaffolding are in place to swap in real JWT auth later.

## Repository layout

```
backend/    FastAPI app, models, Alembic migrations, tests
frontend/   React + Vite SPA
claude_skills/  Vendored skill definitions + INTEGRATION.md (patterns → code map)
```

The four "skills" repos (`obra/superpowers`, `affaan-m/ECC`,
`donnemartin/system-design-primer`, `nextlevelbuilder/ui-ux-pro-max-skill`) are
Claude Code skills / study docs — **not** pip packages. They are vendored under
`claude_skills/` and their *patterns* are implemented in real code. See
[`claude_skills/INTEGRATION.md`](claude_skills/INTEGRATION.md).

## Run locally

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in POSTGRES_*, REDIS_URL, GROQ_API_KEY
alembic upgrade head
uvicorn main:app --reload     # http://localhost:8000  (docs at /docs)
```
Redis and Groq are optional locally — without them the app still boots (caching and
locks no-op; AI endpoints return graceful fallbacks). Tests run fully offline:
```bash
cd backend && pip install pytest && pytest -q
```

### Frontend
Two options locally:

- **Single app** (matches production): `cd frontend && npm run build`, then run the
  backend — FastAPI serves the SPA at http://localhost:8000 alongside the API.
- **Split dev** (hot reload): run the backend on :8000, then
  ```bash
  cd frontend
  npm install
  echo "VITE_API_BASE_URL=http://localhost:8000" > .env   # point the SPA at the API
  npm run dev                                              # http://localhost:5173
  ```
  (Without `VITE_API_BASE_URL` the SPA calls its own origin, which is correct for
  the single-app build but not for the split Vite dev server.)

## Deploy to Render (single app, no Docker / no render.yaml)

The FastAPI backend **serves the built React SPA** from the same process, so the
whole thing is **one Render Web Service** at one URL — the API lives under
`/health`, `/roadmap`, … and the React app is served at `/` (deep links fall back
to `index.html`). No separate frontend service and no CORS needed.

The built frontend (`frontend/dist/`) is committed to the repo, so it works even on
Render's Python runtime (which has no Node). `build.sh` refreshes it automatically
when Node *is* available.

1. **PostgreSQL** — create a Render Postgres instance; copy its *Internal Database URL*.
2. **Redis** *(optional)* — create a Render Key Value (Redis) instance; copy its URL.
3. **Web Service** (this repo)
   - Root Directory: *(leave blank — repo root)*
   - Build Command: `./build.sh`
     (pip install + `alembic upgrade head`, and rebuilds the frontend if Node is present)
   - Start Command: `gunicorn --chdir backend main:app -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:$PORT`
   - **Environment Variables** (add each individually — *not* a Secret File):
     `DATABASE_URL` = the Internal Database URL, plus `REDIS_URL`, `GROQ_API_KEY`,
     `GROQ_MODEL`, `APP_SECRET_KEY`, `APP_ENV=production`. Leave `VITE_API_BASE_URL`
     unset so the SPA calls its own origin. The app auto-rewrites Render's
     `postgres://` URL to the async driver.

> **After changing frontend code**, rebuild and commit the bundle:
> `cd frontend && npm run build`, then commit `frontend/dist/`.

## API overview

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + service status |
| POST | `/users` | Create/update user (returns id for `X-User-Id`) |
| POST/GET | `/roadmap` | Generate / fetch learning roadmap |
| POST/GET/PATCH | `/projects/suggest`, `/projects`, `/projects/{id}` | Project suggestions & status |
| POST | `/resume/build` | Generate a tailored resume |
| POST | `/interview/start`, `/interview/answer` | Mock interview + scoring |
| GET/POST | `/lessons/daily`, `/lessons/{id}/complete` | Daily lessons + completion |

Every response uses a consistent envelope: `{ success, data, message, meta }`.
