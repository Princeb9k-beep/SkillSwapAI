#!/usr/bin/env bash
# Render build command: install deps and apply migrations.
# Set this as the "Build Command" for the Render Web Service (Root Directory = backend).
set -o errexit

pip install -r requirements.txt
alembic upgrade head
