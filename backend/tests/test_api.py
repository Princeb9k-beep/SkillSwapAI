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


def test_signup_login_and_roadmap_flow(client):
    # sign up
    r = client.post(
        "/auth/signup",
        json={"email": "prince@example.com", "password": "supersecret", "name": "Prince"},
    )
    assert r.status_code == 201
    body = r.json()
    _assert_envelope(body)
    token = body["data"]["token"]
    assert token and body["data"]["user"]["email"] == "prince@example.com"

    headers = {"Authorization": f"Bearer {token}"}

    # update goal via authenticated profile endpoint
    r = client.patch("/users/me", json={"goal": "make $80k"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["data"]["goal"] == "make $80k"

    # generate a roadmap (Groq unconfigured -> fallback content, but real DB write)
    r = client.post(
        "/roadmap", json={"goal": "make $80k", "current_skills": []}, headers=headers
    )
    assert r.status_code == 200
    body = r.json()
    _assert_envelope(body)
    assert "milestones" in body["data"]["content"]

    # log in with the same credentials returns a working token
    r = client.post(
        "/auth/login", json={"email": "prince@example.com", "password": "supersecret"}
    )
    assert r.status_code == 200
    login_token = r.json()["data"]["token"]
    r = client.get("/users/me", headers={"Authorization": f"Bearer {login_token}"})
    assert r.status_code == 200
    assert r.json()["data"]["email"] == "prince@example.com"


def test_signup_duplicate_email_conflicts(client):
    payload = {"email": "dupe@example.com", "password": "supersecret"}
    assert client.post("/auth/signup", json=payload).status_code == 201
    r = client.post("/auth/signup", json=payload)
    assert r.status_code == 409
    assert r.json()["success"] is False


def test_login_bad_credentials(client):
    r = client.post("/auth/login", json={"email": "nope@example.com", "password": "whatever"})
    assert r.status_code == 401
    _assert_envelope(r.json())
    assert r.json()["success"] is False


def _auth(client, email, name):
    r = client.post(
        "/auth/signup", json={"email": email, "password": "supersecret", "name": name}
    )
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}


def test_skill_matching_complementary_pair(client):
    # Ana can teach Python, wants Guitar. Ben can teach Guitar, wants Python.
    ana = _auth(client, "ana@example.com", "Ana")
    ben = _auth(client, "ben@example.com", "Ben")

    client.post("/skills", json={"name": "Python", "kind": "have"}, headers=ana)
    client.post("/skills", json={"name": "Guitar", "kind": "want"}, headers=ana)
    client.post("/skills", json={"name": "Guitar", "kind": "have"}, headers=ben)
    client.post("/skills", json={"name": "Python", "kind": "want"}, headers=ben)

    r = client.get("/matches", headers=ana)
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    m = data[0]
    assert m["name"] == "Ben"
    assert m["mutual"] is True
    assert m["they_teach_you"] == ["guitar"]
    assert m["you_teach_them"] == ["python"]
    assert m["compatibility"] == 100  # full two-way coverage


def test_matching_normalizes_case_and_dedupes(client):
    hdr = _auth(client, "cara@example.com", "Cara")
    # duplicate (case-insensitive) add returns the same skill, not a second row
    client.post("/skills", json={"name": "React", "kind": "have"}, headers=hdr)
    client.post("/skills", json={"name": "  react ", "kind": "have"}, headers=hdr)
    r = client.get("/skills", headers=hdr)
    haves = [s for s in r.json()["data"] if s["kind"] == "have"]
    assert len(haves) == 1


def test_matches_empty_without_skills(client):
    hdr = _auth(client, "dan@example.com", "Dan")
    r = client.get("/matches", headers=hdr)
    assert r.status_code == 200
    assert r.json()["data"] == []


def test_gamification_awards_xp_and_achievement(client):
    hdr = _auth(client, "gwen@example.com", "Gwen")

    # start at zero
    r = client.get("/progress", headers=hdr)
    assert r.status_code == 200
    assert r.json()["data"]["xp"] == 0

    # generate today's lessons, then complete one -> XP + streak + achievement
    lessons = client.get("/lessons/daily", headers=hdr).json()["data"]
    assert lessons
    done = client.post(f"/lessons/{lessons[0]['id']}/complete", headers=hdr)
    assert done.status_code == 200
    body = done.json()["data"]
    assert body["xp"] == 20
    assert body["streak"] == 1
    assert "First Steps" in body["new_achievements"]

    # completing the same lesson again does not double-award
    again = client.post(f"/lessons/{lessons[0]['id']}/complete", headers=hdr).json()["data"]
    assert again["xp"] == 20

    prog = client.get("/progress", headers=hdr).json()["data"]
    assert prog["xp"] == 20 and prog["streak"] == 1
    assert any(a["code"] == "first_steps" for a in prog["achievements"])


def test_leaderboard_ranks_by_xp(client):
    hdr = _auth(client, "hank@example.com", "Hank")
    lessons = client.get("/lessons/daily", headers=hdr).json()["data"]
    client.post(f"/lessons/{lessons[0]['id']}/complete", headers=hdr)

    r = client.get("/leaderboard", headers=hdr)
    assert r.status_code == 200
    board = r.json()["data"]
    assert board and board[0]["rank"] == 1
    assert all(
        board[i]["xp"] >= board[i + 1]["xp"] for i in range(len(board) - 1)
    )


def test_community_create_post_and_moderation(client):
    owner = _auth(client, "olive@example.com", "Olive")
    member = _auth(client, "milo@example.com", "Milo")

    # create -> creator auto-joins, counts reflect it
    r = client.post(
        "/communities",
        json={"name": "Python Nerds", "topic": "Coding", "description": "We love snakes"},
        headers=owner,
    )
    assert r.status_code == 201
    cid = r.json()["data"]["id"]
    assert r.json()["data"]["joined"] is True and r.json()["data"]["member_count"] == 1

    # duplicate name conflicts
    dupe = client.post("/communities", json={"name": "python nerds", "topic": "Coding"}, headers=owner)
    assert dupe.status_code == 409

    # member posts (auto-joins)
    p = client.post(f"/communities/{cid}/posts", json={"body": "Hello!"}, headers=member)
    assert p.status_code == 201
    post_id = p.json()["data"]["id"]

    # list now shows 2 members, 1 post, joined for member
    listing = client.get("/communities", headers=member).json()["data"]
    row = next(c for c in listing if c["id"] == cid)
    assert row["member_count"] == 2 and row["post_count"] == 1 and row["joined"] is True

    # a third user cannot delete the member's post
    other = _auth(client, "nia@example.com", "Nia")
    forbidden = client.request(
        "DELETE", f"/communities/{cid}/posts/{post_id}", headers=other
    )
    assert forbidden.status_code == 403

    # community creator CAN delete it (moderation)
    modded = client.request(
        "DELETE", f"/communities/{cid}/posts/{post_id}", headers=owner
    )
    assert modded.status_code == 200
    detail = client.get(f"/communities/{cid}", headers=owner).json()["data"]
    assert detail["posts"] == []


def test_missing_auth_returns_envelope(client):
    r = client.post("/roadmap", json={"goal": "x", "current_skills": []})
    assert r.status_code == 401
    _assert_envelope(r.json())
    assert r.json()["success"] is False
