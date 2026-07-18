#!/usr/bin/env bash
# Render build command for the SINGLE-APP deploy (FastAPI serves the React SPA).
# Set on the Render Web Service with Root Directory left BLANK:
#   Build Command:  ./build.sh
#   Start Command:  gunicorn --chdir backend main:app -k uvicorn.workers.UvicornWorker --bind=0.0.0.0:$PORT
set -o errexit

# 1) Python deps
pip install -r backend/requirements.txt

# 2) Frontend build — only if Node is available in the build image. The repo
#    already ships a prebuilt frontend/dist, so this is a best-effort refresh;
#    if npm is missing (Render's Python runtime), the committed dist is used.
if command -v npm >/dev/null 2>&1; then
  (cd frontend && npm ci && npm run build)
else
  echo "npm not found — using committed frontend/dist"
fi

# 3) Database migrations
(cd backend && alembic upgrade head)
