"""
Smoke tests for the SkillSwap AI backend.

These run fully offline: an in-memory-ish sqlite database (aiosqlite) is created and
migrated via SQLAlchemy metadata, Redis is absent (caching/locks no-op), and Groq is
unconfigured (AI skills fall back to their default payloads). They verify the app
boots, the response envelope is consistent, and the core user flow works end-to-end.

Run:  cd backend && pytest -q
"""

from __future__ import annotations

import os
import pathlib
import sys

# Point the app at a local sqlite DB before importing anything app-related.
_DB = pathlib.Path(__file__).parent / "test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB}"
os.environ.setdefault("GROQ_API_KEY", "")  # ensure AI stays in fallback mode
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import asyncio  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, get_engine  # noqa: E402
import main  # noqa: E402


@pytest.fixture(scope="module")
def client():
    async def _create() -> None:
        async with get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())
    with TestClient(main.app) as c:
        yield c
    if _DB.exists():
        _DB.unlink()


def _assert_envelope(body: dict) -> None:
    assert set(body.keys()) >= {"success", "data", "message", "meta"}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope(body)
    assert body["success"] is True
    assert body["data"]["services"]["database"] == "up"


def test_user_and_roadmap_flow(client):
    # create user
    r = client.post("/users", json={"email": "prince@example.com", "goal": "make $80k"})
    assert r.status_code == 200
    body = r.json()
    _assert_envelope(body)
    user_id = body["data"]["id"]

    # generate a roadmap (Groq unconfigured -> fallback content, but real DB write)
    headers = {"X-User-Id": str(user_id)}
    r = client.post("/roadmap", json={"goal": "make $80k", "current_skills": []}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    _assert_envelope(body)
    assert "milestones" in body["data"]["content"]

    # fetch latest roadmap
    r = client.get("/roadmap", headers=headers)
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_missing_auth_returns_envelope(client):
    r = client.post("/roadmap", json={"goal": "x", "current_skills": []})
    assert r.status_code == 401
    _assert_envelope(r.json())
    assert r.json()["success"] is False
