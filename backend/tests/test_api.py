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
os.environ["ADMIN_EMAILS"] = "mod@example.com,elite-admin@example.com,reminder-admin@example.com"  # admins
os.environ["FREE_AI_TOKENS"] = "3"  # small monthly allowance so exhaustion is testable
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


def test_skill_discover_feed(client):
    me = _auth(client, "disco@example.com", "Disco")
    # Mark Python as already known so it comes back tagged "have".
    client.post("/skills", json={"name": "Python", "kind": "have"}, headers=me)

    r = client.get("/skills/discover", headers=me)
    assert r.status_code == 200
    feed = r.json()["data"]
    assert len(feed) >= 10
    # Every card carries the fields the TikTok-style stream renders.
    first = feed[0]
    for key in ("name", "category", "emoji", "blurb", "hook", "difficulty", "learners", "status"):
        assert key in first
    # New (unknown) skills lead; a "have" skill is pushed toward the end.
    assert feed[0]["status"] is None
    py = next(c for c in feed if c["name"] == "Python")
    assert py["status"] == "have"
    assert py["learners"] >= 1  # our user counts as a learner


def test_official_communities_are_seeded(client):
    # Startup seeding gives brand-new users something real to join on day one.
    me = _auth(client, "seedy@example.com", "Seedy")
    listing = client.get("/communities", headers=me).json()["data"]
    names = {c["name"] for c in listing}
    assert "Welcome to SkillSwap" in names
    assert "Coding & Web Dev" in names
    # Official communities are platform-owned (no creator), so joining is possible.
    welcome = next(c for c in listing if c["name"] == "Welcome to SkillSwap")
    assert welcome["joined"] is False
    joined = client.post(f"/communities/{welcome['id']}/join", headers=me)
    assert joined.status_code == 200


def test_skill_verification_peer_review(client):
    owner = _auth(client, "vera@example.com", "Vera")
    r1 = _auth(client, "rob@example.com", "Rob")
    r2 = _auth(client, "sue@example.com", "Sue")

    # Requesting verification is an Elite feature.
    client.post("/billing/subscribe", json={"tier": "elite"}, headers=owner)
    # owner has the skill and requests verification
    client.post("/skills", json={"name": "Rust", "kind": "have"}, headers=owner)
    req = client.post(
        "/verifications", json={"skill_name": "Rust", "description": "5y experience"}, headers=owner
    )
    assert req.status_code == 201
    rid = req.json()["data"]["id"]

    # owner can't review own request
    assert client.post(f"/verifications/{rid}/review", json={"vote": "approve"}, headers=owner).status_code == 403

    # it appears in a peer's queue
    q = client.get("/verifications/queue", headers=r1).json()["data"]
    assert any(item["id"] == rid for item in q)

    # first approval -> still pending (threshold 2)
    a1 = client.post(f"/verifications/{rid}/review", json={"vote": "approve"}, headers=r1)
    assert a1.json()["data"]["status"] == "pending"
    # double review blocked
    assert client.post(f"/verifications/{rid}/review", json={"vote": "approve"}, headers=r1).status_code == 409

    # second approval -> verified
    a2 = client.post(f"/verifications/{rid}/review", json={"vote": "approve"}, headers=r2)
    assert a2.json()["data"]["status"] == "verified"

    # the owner's skill is now flagged verified + badge awarded
    my_skills = client.get("/skills", headers=owner).json()["data"]
    assert any(s["name"] == "Rust" and s["verified"] for s in my_skills)
    prog = client.get("/progress", headers=owner).json()["data"]
    assert any(a["code"] == "verified_skill" for a in prog["achievements"])


def test_portfolio_aggregates_profile(client):
    hdr = _auth(client, "pat@example.com", "Pat")
    client.patch("/users/me", json={"goal": "make $80k"}, headers=hdr)
    client.post("/skills", json={"name": "Go", "kind": "have"}, headers=hdr)
    client.post("/skills", json={"name": "Kubernetes", "kind": "want"}, headers=hdr)

    r = client.get("/portfolio", headers=hdr)
    assert r.status_code == 200
    p = r.json()["data"]
    assert p["name"] == "Pat" and p["goal"] == "make $80k"
    assert p["level"] == 1 and "xp" in p
    assert [s["name"] for s in p["skills_have"]] == ["Go"]
    assert p["skills_want"] == ["Kubernetes"]
    assert p["verified_count"] == 0


def test_reputation_scoring(client):
    subject = _auth(client, "quinn@example.com", "Quinn")
    r1 = _auth(client, "raj@example.com", "Raj")

    # get subject id via a review flow — reviewer needs subject's id from a match?
    # simplest: subject has no reviews yet -> score None
    sid = client.get("/users/me", headers=subject).json()["data"]["id"]
    empty = client.get(f"/reputation/{sid}", headers=r1).json()["data"]
    assert empty["score"] is None and empty["count"] == 0

    # can't review self
    assert client.post(
        f"/reputation/{sid}/review",
        json={"teaching_quality": 5, "reliability": 5, "response_time": 5},
        headers=subject,
    ).status_code == 403

    # a top review -> score 100
    top = client.post(
        f"/reputation/{sid}/review",
        json={"teaching_quality": 5, "reliability": 5, "response_time": 5, "completed": True,
              "comment": "Fantastic teacher"},
        headers=r1,
    )
    assert top.status_code == 201
    assert top.json()["data"]["score"] == 100 and top.json()["data"]["count"] == 1

    # a weak review pulls the average down
    r2 = _auth(client, "sam@example.com", "Sam")
    client.post(
        f"/reputation/{sid}/review",
        json={"teaching_quality": 1, "reliability": 1, "response_time": 1, "completed": False},
        headers=r2,
    )
    summary = client.get(f"/reputation/{sid}", headers=r1).json()["data"]
    assert 0 < summary["score"] < 100 and summary["count"] == 2
    assert any(rv["comment"] == "Fantastic teacher" for rv in summary["reviews"])

    # portfolio surfaces reputation
    port = client.get("/portfolio", headers=subject).json()["data"]
    assert port["reputation"]["count"] == 2


def test_marketplace_listing_booking_and_commission(client):
    seller = _auth(client, "tess@example.com", "Tess")
    buyer = _auth(client, "uri@example.com", "Uri")

    # seller creates a $50.00 tutoring listing
    lst = client.post(
        "/marketplace/listings",
        json={"title": "Python tutoring", "kind": "tutoring", "price_cents": 5000},
        headers=seller,
    )
    assert lst.status_code == 201
    lid = lst.json()["data"]["id"]

    # it appears for the buyer, not for the seller (own listings excluded)
    assert any(l["id"] == lid for l in client.get("/marketplace/listings", headers=buyer).json()["data"])
    assert all(l["id"] != lid for l in client.get("/marketplace/listings", headers=seller).json()["data"])

    # seller can't book own listing
    assert client.post(f"/marketplace/listings/{lid}/book", headers=seller).status_code == 403

    # buyer books -> order with 15% commission ($7.50)
    order = client.post(f"/marketplace/listings/{lid}/book", headers=buyer)
    assert order.status_code == 201
    od = order.json()["data"]
    oid = od["id"]
    assert od["price_cents"] == 5000 and od["commission_cents"] == 750
    assert od["seller_net_cents"] == 4250 and od["status"] == "requested" and od["paid"] is False

    # buyer can't confirm (seller-only); seller confirms
    assert client.patch(f"/marketplace/orders/{oid}", json={"status": "confirmed"}, headers=buyer).status_code == 403
    assert client.patch(f"/marketplace/orders/{oid}", json={"status": "confirmed"}, headers=seller).json()["data"]["status"] == "confirmed"

    # orders show up on both sides
    seller_orders = client.get("/marketplace/orders", headers=seller).json()["data"]
    buyer_orders = client.get("/marketplace/orders", headers=buyer).json()["data"]
    assert len(seller_orders["as_seller"]) == 1 and len(buyer_orders["as_buyer"]) == 1


def test_ai_coach_chat_persists_and_degrades(client):
    hdr = _auth(client, "cora@example.com", "Cora")

    # empty history to start
    assert client.get("/coach/history", headers=hdr).json()["data"] == []

    # chat -> reply (Groq unconfigured in tests -> graceful fallback, not a crash)
    r = client.post("/coach/chat", json={"message": "How do I learn Python?"}, headers=hdr)
    assert r.status_code == 200
    reply = r.json()["data"]["reply"]
    assert isinstance(reply, str) and reply

    # history now has the user turn + assistant turn, in order
    hist = client.get("/coach/history", headers=hdr).json()["data"]
    assert [m["role"] for m in hist] == ["user", "assistant"]
    assert hist[0]["content"] == "How do I learn Python?"

    # clear
    assert client.delete("/coach/history", headers=hdr).status_code == 200
    assert client.get("/coach/history", headers=hdr).json()["data"] == []


def test_skill_scanner_returns_structure(client):
    hdr = _auth(client, "sid@example.com", "Sid")
    r = client.post(
        "/scanner/analyze",
        json={"text": "Backend engineer with 5 years of Python, FastAPI and PostgreSQL."},
        headers=hdr,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    # Groq unconfigured in tests -> graceful fallback, but the shape is stable
    assert set(["summary", "strengths", "missing", "next_steps"]).issubset(data)
    assert isinstance(data["strengths"], list) and isinstance(data["next_steps"], list)

    # too-short input is rejected by validation
    assert client.post("/scanner/analyze", json={"text": "hi"}, headers=hdr).status_code == 422


def test_daily_challenge_completion_awards_xp(client):
    hdr = _auth(client, "cleo@example.com", "Cleo")

    # today's challenge generated once and stable across calls
    first = client.get("/challenges/today", headers=hdr).json()["data"]
    assert first["title"] and first["completed"] is False
    again = client.get("/challenges/today", headers=hdr).json()["data"]
    assert again["id"] == first["id"]

    # complete -> XP + streak
    done = client.post(f"/challenges/{first['id']}/complete", headers=hdr).json()["data"]
    assert done["completed"] is True and done["xp"] == 15 and done["streak"] == 1

    # completing again does not double-award
    again2 = client.post(f"/challenges/{first['id']}/complete", headers=hdr).json()["data"]
    assert again2["xp"] == 15

    prog = client.get("/progress", headers=hdr).json()["data"]
    assert prog["xp"] == 15


def test_ai_twin_train_chat_quiz(client):
    owner = _auth(client, "tara@example.com", "Tara")
    learner = _auth(client, "leo@example.com", "Leo")

    # Training your twin is Elite; chatting with a twin is Pro.
    client.post("/billing/subscribe", json={"tier": "elite"}, headers=owner)
    client.post("/billing/subscribe", json={"tier": "pro"}, headers=learner)
    # owner has a skill and trains their twin
    client.post("/skills", json={"name": "Guitar", "kind": "have"}, headers=owner)
    assert client.get("/twin/me", headers=owner).json()["data"]["trained"] is False
    trained = client.post(
        "/twin/train",
        json={"samples": "I teach guitar with simple analogies and lots of encouragement."},
        headers=owner,
    )
    assert trained.status_code == 200 and trained.json()["data"]["trained"] is True

    owner_id = client.get("/users/me", headers=owner).json()["data"]["id"]

    # the owner's twin appears in the learner's available list
    avail = client.get("/twin/available", headers=learner).json()["data"]
    assert any(t["owner_id"] == owner_id and "Guitar" in t["skills"] for t in avail)

    # learner chats with the twin -> reply (fallback without Groq), history persists
    r = client.post(f"/twin/{owner_id}/chat", json={"message": "How do I start?"}, headers=learner)
    assert r.status_code == 200 and r.json()["data"]["reply"]
    hist = client.get(f"/twin/{owner_id}/history", headers=learner).json()["data"]
    assert [m["role"] for m in hist] == ["user", "assistant"]

    # quiz in the twin's style
    q = client.post(f"/twin/{owner_id}/quiz", json={"topic": "chords"}, headers=learner)
    assert q.status_code == 200 and len(q.json()["data"]["questions"]) >= 1

    # untrained twin isn't chattable
    assert client.post(f"/twin/{owner_id}/chat", json={"message": "x"}, headers=owner).status_code in (200, 404)
    fresh = _auth(client, "nooo@example.com", "Noo")
    nid = client.get("/users/me", headers=fresh).json()["data"]["id"]
    assert client.post(f"/twin/{nid}/chat", json={"message": "x"}, headers=learner).status_code == 404


def test_translation(client):
    hdr = _auth(client, "tom@example.com", "Tom")
    langs = client.get("/translate/languages", headers=hdr).json()["data"]
    assert "Spanish" in langs

    # Groq unconfigured -> graceful fallback returns the original + a stable shape
    r = client.post(
        "/translate", json={"text": "Hello, friend", "target_language": "Spanish"}, headers=hdr
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["target_language"] == "Spanish" and isinstance(data["translation"], str)


def test_practice_rooms_lobby(client):
    host = _auth(client, "roomhost@example.com", "Room Host")
    guest = _auth(client, "roomguest@example.com", "Room Guest")
    client.post("/billing/subscribe", json={"tier": "pro"}, headers=host)  # rooms are Pro

    # Create a room.
    r = client.post("/rooms", json={"title": "Mock interview", "topic": "Careers"}, headers=host)
    assert r.status_code == 201
    room = r.json()["data"]
    code = room["code"]
    assert room["title"] == "Mock interview" and room["is_open"] is True

    # It shows up in the open lobby.
    listed = client.get("/rooms", headers=guest).json()["data"]
    assert any(x["code"] == code for x in listed)

    # Detail carries shared notes.
    detail = client.get(f"/rooms/{code}", headers=guest).json()["data"]
    assert detail["code"] == code and "notes" in detail

    # Notes persist.
    assert client.put(f"/rooms/{code}/notes", json={"notes": "agenda"}, headers=host).status_code == 200
    assert client.get(f"/rooms/{code}", headers=host).json()["data"]["notes"] == "agenda"

    # Only the host can close it.
    assert client.post(f"/rooms/{code}/close", headers=guest).status_code == 403
    assert client.post(f"/rooms/{code}/close", headers=host).status_code == 200

    # Closed rooms drop out of the lobby.
    listed_after = client.get("/rooms", headers=host).json()["data"]
    assert all(x["code"] != code for x in listed_after)


def test_practice_room_signaling(client):
    host = _auth(client, "sig1@example.com", "Sig One")
    client.post("/billing/subscribe", json={"tier": "pro"}, headers=host)
    uid = client.get("/users/me", headers=host).json()["data"]["id"]
    code = client.post("/rooms", json={"title": "Pairing"}, headers=host).json()["data"]["code"]

    # The signaling socket greets a peer with a welcome + the current peer list.
    with client.websocket_connect(f"/rooms/ws/{code}?uid={uid}") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "welcome"
        assert isinstance(hello["peers"], list) and "peer_id" in hello


def test_practice_room_signaling_rejects_unauthenticated(client):
    host = _auth(client, "sig2@example.com", "Sig Two")
    client.post("/billing/subscribe", json={"tier": "pro"}, headers=host)
    code = client.post("/rooms", json={"title": "Locked"}, headers=host).json()["data"]["code"]
    with client.websocket_connect(f"/rooms/ws/{code}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "error"


def test_direct_messaging_flow(client):
    alice = _auth(client, "msgalice@example.com", "Msg Alice")
    bob = _auth(client, "msgbob@example.com", "Msg Bob")
    alice_id = client.get("/users/me", headers=alice).json()["data"]["id"]
    bob_id = client.get("/users/me", headers=bob).json()["data"]["id"]

    # Alice messages Bob.
    r = client.post(f"/messages/{bob_id}", json={"body": "hi Bob"}, headers=alice)
    assert r.status_code == 201 and r.json()["data"]["mine"] is True

    # Bob sees one unread thread from Alice.
    threads = client.get("/messages/threads", headers=bob).json()["data"]
    assert len(threads) == 1
    t = threads[0]
    assert t["partner_id"] == alice_id and t["unread"] == 1 and t["last_message"] == "hi Bob"
    assert client.get("/messages/unread/count", headers=bob).json()["data"]["unread"] == 1

    # Opening the conversation marks it read.
    convo = client.get(f"/messages/{alice_id}", headers=bob).json()["data"]
    assert convo["partner_name"] == "Msg Alice"
    assert [m["body"] for m in convo["messages"]] == ["hi Bob"]
    assert client.get("/messages/unread/count", headers=bob).json()["data"]["unread"] == 0

    # Bob replies; Alice's view shows both, ordered oldest-first.
    client.post(f"/messages/{alice_id}", json={"body": "hey Alice"}, headers=bob)
    convo_a = client.get(f"/messages/{bob_id}", headers=alice).json()["data"]
    assert [m["body"] for m in convo_a["messages"]] == ["hi Bob", "hey Alice"]

    # Guardrails: no self-messaging, unknown recipient 404.
    assert client.post(f"/messages/{alice_id}", json={"body": "me"}, headers=alice).status_code == 400
    assert client.post("/messages/999999", json={"body": "ghost"}, headers=alice).status_code == 404


def test_notifications_welcome_and_message_and_prefs(client):
    ana = _auth(client, "notifana@example.com", "Notif Ana")
    bob = _auth(client, "notifbob@example.com", "Notif Bob")
    ana_id = client.get("/users/me", headers=ana).json()["data"]["id"]
    bob_id = client.get("/users/me", headers=bob).json()["data"]["id"]

    # Signup seeds a welcome notification.
    notes = client.get("/notifications", headers=bob).json()
    assert notes["meta"]["unread"] == 1
    assert notes["data"][0]["type"] == "welcome"

    # A message to Bob creates a notification for him.
    client.post(f"/messages/{bob_id}", json={"body": "hello"}, headers=ana)
    assert client.get("/notifications/unread/count", headers=bob).json()["data"]["unread"] == 2
    top = client.get("/notifications", headers=bob).json()["data"][0]
    assert top["type"] == "message" and "Notif Ana" in top["title"]
    assert top["link"] == f"/messages?to={ana_id}&name=Notif%20Ana"

    # Mark one read, then mark all read.
    assert client.post(f"/notifications/{top['id']}/read", headers=bob).status_code == 200
    assert client.get("/notifications/unread/count", headers=bob).json()["data"]["unread"] == 1
    assert client.post("/notifications/read-all", headers=bob).status_code == 200
    assert client.get("/notifications/unread/count", headers=bob).json()["data"]["unread"] == 0

    # Muting message alerts suppresses new message notifications.
    client.patch("/users/me", json={"notify_messages": False}, headers=bob)
    assert client.get("/users/me", headers=bob).json()["data"]["notify_messages"] is False
    client.post(f"/messages/{bob_id}", json={"body": "again"}, headers=ana)
    assert client.get("/notifications/unread/count", headers=bob).json()["data"]["unread"] == 0


def test_notification_read_forbidden_for_other_user(client):
    ana = _auth(client, "notifx@example.com", "Notif X")
    bob = _auth(client, "notify@example.com", "Notif Y")
    # Bob has a welcome notification; Ana can't mark it read.
    nid = client.get("/notifications", headers=bob).json()["data"][0]["id"]
    assert client.post(f"/notifications/{nid}/read", headers=ana).status_code == 404


def test_push_subscription_management(client):
    hdr = _auth(client, "pushuser@example.com", "Push User")

    # VAPID unconfigured in tests -> public key is null (push disabled, degrades).
    key = client.get("/push/vapid-public-key", headers=hdr).json()["data"]["public_key"]
    assert key is None

    sub = {
        "endpoint": "https://push.example.com/sub/abc",
        "keys": {"p256dh": "BPa...key", "auth": "authsecret"},
    }
    assert client.post("/push/subscribe", json=sub, headers=hdr).status_code == 201
    # Re-subscribing the same endpoint is idempotent (update, not error).
    assert client.post("/push/subscribe", json=sub, headers=hdr).status_code == 201

    # Missing encryption keys -> 422.
    bad = {"endpoint": "https://push.example.com/sub/bad", "keys": {}}
    assert client.post("/push/subscribe", json=bad, headers=hdr).status_code == 422

    # Unsubscribe removes it.
    r = client.post(
        "/push/unsubscribe", json={"endpoint": sub["endpoint"]}, headers=hdr
    )
    assert r.status_code == 200


def test_message_send_survives_push_when_unconfigured(client):
    ana = _auth(client, "pushana@example.com", "Push Ana")
    bob = _auth(client, "pushbob@example.com", "Push Bob")
    bob_id = client.get("/users/me", headers=bob).json()["data"]["id"]

    # Bob has a push subscription, but VAPID is unconfigured -> push is a no-op
    # and sending the message must still succeed.
    client.post(
        "/push/subscribe",
        json={
            "endpoint": "https://push.example.com/sub/bob",
            "keys": {"p256dh": "BPa...key", "auth": "authsecret"},
        },
        headers=bob,
    )
    r = client.post(f"/messages/{bob_id}", json={"body": "ping"}, headers=ana)
    assert r.status_code == 201


def test_onboarding_flag(client):
    hdr = _auth(client, "onboardme@example.com", "Onboard Me")
    # New users start un-onboarded.
    me = client.get("/users/me", headers=hdr).json()["data"]
    assert me["onboarded"] is False
    # Completing onboarding persists the flag.
    r = client.patch("/users/me", json={"onboarded": True}, headers=hdr)
    assert r.status_code == 200 and r.json()["data"]["onboarded"] is True
    assert client.get("/users/me", headers=hdr).json()["data"]["onboarded"] is True


def test_match_signals_dismiss_and_mutual_interest(client):
    # Ana and Ben are a complementary pair.
    ana = _auth(client, "sigana@example.com", "Sig Ana")
    ben = _auth(client, "sigben@example.com", "Sig Ben")
    ana_id = client.get("/users/me", headers=ana).json()["data"]["id"]
    ben_id = client.get("/users/me", headers=ben).json()["data"]["id"]

    client.post("/skills", json={"name": "Python", "kind": "have"}, headers=ana)
    client.post("/skills", json={"name": "Guitar", "kind": "want"}, headers=ana)
    client.post("/skills", json={"name": "Guitar", "kind": "have"}, headers=ben)
    client.post("/skills", json={"name": "Python", "kind": "want"}, headers=ben)

    # Ana sees Ben.
    assert any(m["user_id"] == ben_id for m in client.get("/matches", headers=ana).json()["data"])

    # Both mark each other interested -> mutual interest surfaces for Ana.
    assert client.post(f"/matches/{ben_id}/feedback", json={"signal": "interested"}, headers=ana).status_code == 200
    client.post(f"/matches/{ana_id}/feedback", json={"signal": "interested"}, headers=ben)
    ana_view = [m for m in client.get("/matches", headers=ana).json()["data"] if m["user_id"] == ben_id][0]
    assert ana_view["interested"] is True and ana_view["mutual_interest"] is True
    assert "match_score" in ana_view

    # Ana dismisses Ben -> Ben disappears from Ana's matches.
    assert client.post(f"/matches/{ben_id}/feedback", json={"signal": "dismissed"}, headers=ana).status_code == 200
    assert all(m["user_id"] != ben_id for m in client.get("/matches", headers=ana).json()["data"])

    # Guardrails.
    assert client.post(f"/matches/{ana_id}/feedback", json={"signal": "interested"}, headers=ana).status_code == 400
    assert client.post("/matches/999999/feedback", json={"signal": "interested"}, headers=ana).status_code == 404
    assert client.post(f"/matches/{ben_id}/feedback", json={"signal": "nope"}, headers=ana).status_code == 422


def test_meetups_create_rsvp_capacity(client):
    host = _auth(client, "meethost@example.com", "Meet Host")
    guest = _auth(client, "meetguest@example.com", "Meet Guest")
    third = _auth(client, "meetthird@example.com", "Meet Third")

    r = client.post(
        "/meetups",
        json={
            "title": "Python study night",
            "location": "Online",
            "starts_at": "2099-01-01T18:00:00+00:00",
            "capacity": 2,
        },
        headers=host,
    )
    assert r.status_code == 201
    mid = r.json()["data"]["id"]
    # Host is auto-RSVP'd (attendee_count 1, capacity 2).
    listed = client.get("/meetups", headers=guest).json()["data"]
    m = next(x for x in listed if x["id"] == mid)
    assert m["attendee_count"] == 1 and m["joined"] is False

    # Guest fills the last seat.
    assert client.post(f"/meetups/{mid}/rsvp", headers=guest).status_code == 200
    # Third is turned away (full).
    assert client.post(f"/meetups/{mid}/rsvp", headers=third).status_code == 409
    # Guest cancels, third can now join.
    assert client.post(f"/meetups/{mid}/cancel", headers=guest).status_code == 200
    assert client.post(f"/meetups/{mid}/rsvp", headers=third).status_code == 200
    # Non-host can't delete.
    assert client.delete(f"/meetups/{mid}", headers=third).status_code == 403
    assert client.delete(f"/meetups/{mid}", headers=host).status_code == 200


def test_partnerships_flow(client):
    owner = _auth(client, "coowner@example.com", "Co Owner")
    learner = _auth(client, "colearner@example.com", "Co Learner")

    cid = client.post(
        "/partnerships/companies",
        json={"name": "Acme", "website": "https://acme.test"},
        headers=owner,
    ).json()["data"]["id"]

    # Only the owner can post a challenge.
    body = {"title": "Build a CLI", "kind": "internship", "reward": "Interview"}
    assert client.post(f"/partnerships/companies/{cid}/challenges", json=body, headers=learner).status_code == 403
    chid = client.post(f"/partnerships/companies/{cid}/challenges", json=body, headers=owner).json()["data"]["id"]

    # It shows in the open list with kind + company.
    opps = client.get("/partnerships/challenges", headers=learner).json()["data"]
    opp = next(o for o in opps if o["id"] == chid)
    assert opp["kind"] == "internship" and opp["company_name"] == "Acme" and opp["my_status"] is None

    # Learner submits; owner sees + accepts it.
    assert client.post(f"/partnerships/challenges/{chid}/submit", json={"content": "github.com/me/cli"}, headers=learner).status_code == 201
    assert client.get("/partnerships/challenges", headers=learner).json()["data"]
    my = next(o for o in client.get("/partnerships/challenges", headers=learner).json()["data"] if o["id"] == chid)
    assert my["my_status"] == "submitted"

    # Learner can't view submissions; owner can.
    assert client.get(f"/partnerships/challenges/{chid}/submissions", headers=learner).status_code == 403
    subs = client.get(f"/partnerships/challenges/{chid}/submissions", headers=owner).json()["data"]
    assert len(subs) == 1 and subs[0]["status"] == "submitted"
    sub_id = subs[0]["id"]
    assert client.post(f"/partnerships/submissions/{sub_id}/review", json={"status": "accepted"}, headers=owner).status_code == 200
    # Reflected in the learner's view.
    my2 = next(o for o in client.get("/partnerships/challenges", headers=learner).json()["data"] if o["id"] == chid)
    assert my2["my_status"] == "accepted"


def test_email_verification_flow(client):
    r = client.post(
        "/auth/signup",
        json={"email": "verifyme@example.com", "password": "supersecret123", "name": "V"},
    )
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["user"]["email_verified"] is False
    token = data["dev_token"]  # returned outside production
    hdr = {"Authorization": f"Bearer {token}"}

    # A verification token can't be used as an access token.
    assert client.get("/users/me", headers=hdr).status_code == 401

    # Verify with the token.
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    access = {"Authorization": f"Bearer {data['token']}"}
    assert client.get("/users/me", headers=access).json()["data"]["email_verified"] is True

    # Bad token is rejected.
    assert client.post("/auth/verify-email", json={"token": "garbage"}).status_code == 400


def test_resend_verification_reports_outcome(client, monkeypatch):
    """Resend tells the truth about delivery, and works even with no provider."""
    import app.routers.auth as auth_router

    def _signup(email):
        r = client.post(
            "/auth/signup",
            json={"email": email, "password": "supersecret123", "name": "R"},
        )
        return {"Authorization": f"Bearer {r.json()['data']['token']}"}

    # (1) No SMTP configured → the user is verified inline (free, no provider).
    monkeypatch.setattr(auth_router, "email_configured", lambda: False)
    a = _signup("noconfig@example.com")
    body = client.post("/auth/resend-verification", headers=a).json()["data"]
    assert body["email_configured"] is False and body["verified"] is True
    assert client.get("/users/me", headers=a).json()["data"]["email_verified"] is True

    # (2) SMTP configured and the provider accepts → reported as sent.
    async def _ok_send(to, name, token):
        return True

    monkeypatch.setattr(auth_router, "email_configured", lambda: True)
    monkeypatch.setattr(auth_router, "send_verification_email", _ok_send)
    b = _signup("okmail@example.com")
    ok_body = client.post("/auth/resend-verification", headers=b).json()
    assert ok_body["success"] is True and ok_body["data"]["email_sent"] is True

    # (3) SMTP configured but the send fails → a real error, not a fake success.
    async def _fail_send(to, name, token):
        return False

    monkeypatch.setattr(auth_router, "send_verification_email", _fail_send)
    c = _signup("failmail@example.com")
    fail = client.post("/auth/resend-verification", headers=c)
    assert fail.status_code == 502
    assert fail.json()["meta"]["code"] == "email_send_failed"


def test_signup_sends_email_when_configured(client, monkeypatch):
    """When SMTP is configured the verification link is emailed and the token is
    NOT returned to the client."""
    import app.routers.auth as auth_router

    sent = {}

    async def _fake_send(to, name, token):
        sent["to"] = to
        sent["token"] = token
        return True

    monkeypatch.setattr(auth_router, "email_configured", lambda: True)
    monkeypatch.setattr(auth_router, "send_verification_email", _fake_send)

    r = client.post(
        "/auth/signup",
        json={"email": "emailed@example.com", "password": "supersecret123", "name": "E"},
    )
    assert r.status_code == 201
    data = r.json()["data"]
    # The token was emailed, so it must not leak in the response.
    assert "dev_token" not in data
    # The email is sent on a background task — drive the loop until it runs.
    for _ in range(50):
        if sent:
            break
        client.get("/health")
    assert sent["to"] == "emailed@example.com" and sent["token"]


def test_global_search(client):
    owner = _auth(client, "searchteacher@example.com", "Ada Searchable")
    client.post("/skills", json={"name": "Rust", "kind": "have", "level": "advanced"}, headers=owner)

    seeker = _auth(client, "searchseeker@example.com", "Seeker")
    # Find the person by their teachable skill.
    by_skill = client.get("/search?q=Rust", headers=seeker).json()["data"]
    assert any(p["name"] == "Ada Searchable" for p in by_skill["people"])
    # Find them by name.
    by_name = client.get("/search?q=Searchable", headers=seeker).json()["data"]
    assert any(p["name"] == "Ada Searchable" for p in by_name["people"])
    # Academy courses are searchable too.
    courses = client.get("/search?q=Python", headers=seeker).json()["data"]["courses"]
    assert len(courses) >= 1
    # Too-short queries are rejected.
    assert client.get("/search?q=a", headers=seeker).status_code == 422


def test_refresh_token_flow(client):
    email = "refresh@example.com"
    signup = client.post(
        "/auth/signup", json={"email": email, "password": "supersecret1", "name": "Refresh"}
    ).json()["data"]
    assert signup["token"] and signup["refresh_token"]
    refresh = signup["refresh_token"]

    # Refresh rotates: new access + a NEW refresh token; the old one is now dead.
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    new = r.json()["data"]
    assert new["token"] and new["refresh_token"] != refresh
    assert client.post("/auth/refresh", json={"refresh_token": refresh}).status_code == 401

    # The new access token works.
    hdr = {"Authorization": f"Bearer {new['token']}"}
    assert client.get("/users/me", headers=hdr).status_code == 200

    # Sessions count reflects active refresh tokens; logout-all clears them.
    assert client.get("/auth/sessions", headers=hdr).json()["data"]["active"] >= 1
    client.post("/auth/logout-all", headers=hdr)
    assert client.get("/auth/sessions", headers=hdr).json()["data"]["active"] == 0
    assert client.post("/auth/refresh", json={"refresh_token": new["refresh_token"]}).status_code == 401


def test_logout_revokes_refresh(client):
    login = client.post("/auth/signup", json={"email": "logout@example.com", "password": "supersecret1"}).json()["data"]
    client.post("/auth/logout", json={"refresh_token": login["refresh_token"]})
    assert client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]}).status_code == 401


def test_oauth_providers_and_gating(client):
    # No OAuth env configured in tests -> no providers offered.
    provs = client.get("/auth/oauth/providers").json()["data"]["providers"]
    assert provs == []
    # Starting a disabled provider 404s; callback on a disabled provider too.
    assert client.get("/auth/oauth/google/start").status_code == 404
    assert client.post("/auth/oauth/github/callback", json={"code": "x"}).status_code == 404


def test_daily_reminders(client):
    hdr = _auth(client, "reminders@example.com", "Reminder User")
    # Opt in via profile.
    upd = client.patch("/users/me", json={"daily_reminder": True}, headers=hdr)
    assert upd.status_code == 200 and upd.json()["data"]["daily_reminder"] is True

    # Admin can trigger the run; the opted-in user gets a reminder notification.
    admin = _auth(client, "reminder-admin@example.com", "Reminder Admin")
    r = client.post("/reminders/run", headers=admin)
    assert r.status_code == 200 and r.json()["data"]["sent"] >= 1

    notes = client.get("/notifications", headers=hdr).json()["data"]
    assert any(n["type"] == "reminder" for n in notes)

    # Second run the same day is idempotent — this user isn't reminded again.
    before = len([n for n in notes if n["type"] == "reminder"])
    client.post("/reminders/run", headers=admin)
    notes2 = client.get("/notifications", headers=hdr).json()["data"]
    assert len([n for n in notes2 if n["type"] == "reminder"]) == before

    # Without the secret or admin, the endpoint is forbidden.
    assert client.post("/reminders/run", headers=hdr).status_code == 403


def test_ai_skill_assessment(client):
    hdr = _auth(client, "assess@example.com", "Assess User")
    client.post("/billing/subscribe", json={"tier": "elite"}, headers=hdr)  # verification is Elite
    client.post("/skills", json={"name": "Python", "kind": "have", "level": "advanced"}, headers=hdr)

    quiz = client.post("/verifications/assessment", json={"skill_name": "Python"}, headers=hdr)
    assert quiz.status_code == 201
    q = quiz.json()["data"]
    assert q["questions"] and "answer" not in q["questions"][0]  # answer key hidden

    # Groq is unconfigured in tests, so generate_quiz returns the deterministic
    # fallback quiz whose correct answers are known.
    answers = [3, 2, 2, 2, 2]
    res = client.post(f"/verifications/assessment/{q['id']}/submit", json={"answers": answers}, headers=hdr)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["passed"] is True and data["score"] == data["total"]

    # The Python skill is now verified.
    skills = client.get("/skills", headers=hdr).json()["data"]
    assert any(s["name"] == "Python" and s["verified"] for s in skills)

    # Re-submitting the finished assessment is rejected.
    assert client.post(f"/verifications/assessment/{q['id']}/submit", json={"answers": answers}, headers=hdr).status_code == 409


def test_scanner_file_upload(client):
    hdr = _auth(client, "fileuser@example.com", "File User")
    content = (
        "Experienced Python backend engineer. Built FastAPI services, PostgreSQL "
        "schemas, and Redis caching. Seeking to grow into data engineering."
    ).encode()
    files = {"file": ("resume.txt", content, "text/plain")}
    r = client.post("/scanner/analyze-file", files=files, headers=hdr)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["source"] == "resume.txt"
    assert "summary" in data or "strengths" in data

    # An unsupported binary type is rejected cleanly.
    bad = {"file": ("photo.png", b"\x89PNG\r\n\x1a\n", "image/png")}
    assert client.post("/scanner/analyze-file", files=bad, headers=hdr).status_code == 400


def test_coach_file_critique(client):
    hdr = _auth(client, "coachfile@example.com", "Coach File")
    files = {"file": ("notes.md", b"# My project\nA todo app in React with no tests yet.", "text/markdown")}
    r = client.post("/coach/critique", files=files, data={"note": "Review this"}, headers=hdr)
    assert r.status_code == 200
    assert "reply" in r.json()["data"]


def test_message_emails_recipient(client, monkeypatch):
    """A new message triggers a pref-gated email to the recipient."""
    import app.routers.messages as messages_router

    sent = []

    async def _fake(user, type, title, body, link):
        sent.append((user.email, type, title))
        return True

    monkeypatch.setattr(messages_router, "send_event_email", _fake)

    a = _auth(client, "mail_a@example.com", "Mail A")
    b = _auth(client, "mail_b@example.com", "Mail B")
    b_id = client.get("/users/me", headers=b).json()["data"]["id"]
    assert client.post(f"/messages/{b_id}", json={"body": "ping"}, headers=a).status_code == 201
    # Email is delivered on a background task now — drive the loop until it runs.
    for _ in range(50):
        if sent:
            break
        client.get("/health")
    assert sent and sent[0][0] == "mail_b@example.com" and sent[0][1] == "message"


def test_peer_endorsements(client):
    subject = _auth(client, "endorse_subj@example.com", "Endorse Subject")
    client.post("/skills", json={"name": "Python", "kind": "have"}, headers=subject)
    subj_id = client.get("/users/me", headers=subject).json()["data"]["id"]

    endorser = _auth(client, "endorser@example.com", "Endorser")
    # Can't endorse yourself.
    assert client.post(f"/users/{subj_id}/endorse", json={"skill": "Python"}, headers=subject).status_code == 400
    # Endorse works; duplicate is rejected.
    r = client.post(f"/users/{subj_id}/endorse", json={"skill": "Python"}, headers=endorser)
    assert r.status_code == 200 and r.json()["data"]["endorsements"] == 1
    assert client.post(f"/users/{subj_id}/endorse", json={"skill": "Python"}, headers=endorser).status_code == 409
    # Count shows on the public profile skill.
    prof = client.get(f"/users/{subj_id}/profile", headers=endorser).json()["data"]
    py = next(s for s in prof["skills"] if s["name"] == "Python")
    assert py["endorsements"] == 1


def test_course_certificate(client):
    hdr = _auth(client, "certuser@example.com", "Cert User")
    client.post("/billing/subscribe", json={"tier": "elite"}, headers=hdr)
    slug = client.get("/academy/paths", headers=hdr).json()["data"][0]["slug"]
    client.post(f"/academy/paths/{slug}/enroll", headers=hdr)

    path = client.get(f"/academy/paths/{slug}", headers=hdr).json()["data"]
    keys = [l["key"] for m in path["modules"] for l in m["lessons"]]
    last = None
    for k in keys:
        last = client.post(f"/academy/paths/{slug}/lessons/{k}/complete", headers=hdr).json()["data"]
    assert last["progress"] == 100 and last["certificate_code"]

    certs = client.get("/certificates", headers=hdr).json()["data"]
    assert len(certs) == 1
    # Public verify (no auth) returns the holder + title.
    v = client.get(f"/certificates/verify/{last['certificate_code']}")
    assert v.status_code == 200 and v.json()["data"]["holder"] == "Cert User"
    assert client.get("/certificates/verify/deadbeef").status_code == 404


def test_buddy_shared_streak(client):
    a = _auth(client, "buddy_a@example.com", "Buddy A")
    b = _auth(client, "buddy_b@example.com", "Buddy B")
    b_id = client.get("/users/me", headers=b).json()["data"]["id"]

    inv = client.post("/buddies", json={"partner_id": b_id}, headers=a)
    assert inv.status_code == 201 and inv.json()["data"]["status"] == "pending"
    bid = inv.json()["data"]["id"]

    # Only the invited partner can accept.
    assert client.post(f"/buddies/{bid}/accept", headers=a).status_code == 404
    assert client.post(f"/buddies/{bid}/accept", headers=b).json()["data"]["status"] == "active"

    # One-sided check-in doesn't advance the shared streak.
    r = client.post(f"/buddies/{bid}/checkin", headers=a).json()["data"]
    assert r["advanced"] is False and r["streak"] == 0
    # Both checked in today -> streak advances to 1.
    r2 = client.post(f"/buddies/{bid}/checkin", headers=b).json()["data"]
    assert r2["advanced"] is True and r2["streak"] == 1 and r2["both_today"] is True

    # Duplicate invite is rejected.
    assert client.post("/buddies", json={"partner_id": b_id}, headers=a).status_code == 409

    # Both see the pairing with the shared streak.
    mine = client.get("/buddies", headers=a).json()["data"]
    assert mine[0]["streak"] == 1 and mine[0]["partner_name"] == "Buddy B"


def test_activity_feed_and_kudos(client):
    doer = _auth(client, "feeddoer@example.com", "Feed Doer")
    client.post("/billing/subscribe", json={"tier": "elite"}, headers=doer)
    client.post("/skills", json={"name": "Rust", "kind": "have", "level": "advanced"}, headers=doer)
    q = client.post("/verifications/assessment", json={"skill_name": "Rust"}, headers=doer).json()["data"]
    # Passing the assessment records a "verified" activity.
    client.post(f"/verifications/assessment/{q['id']}/submit", json={"answers": [3, 2, 2, 2, 2]}, headers=doer)

    viewer = _auth(client, "feedviewer@example.com", "Feed Viewer")
    feed = client.get("/feed", headers=viewer).json()["data"]
    act = next((a for a in feed if a["kind"] == "verified"), None)
    assert act and act["kudos"] == 0 and act["kudoed"] is False

    # Kudos toggles on and off.
    k = client.post(f"/feed/{act['id']}/kudos", headers=viewer).json()["data"]
    assert k["kudos"] == 1 and k["kudoed"] is True
    k2 = client.post(f"/feed/{act['id']}/kudos", headers=viewer).json()["data"]
    assert k2["kudos"] == 0 and k2["kudoed"] is False


def test_timezone_localized_session_notification(client):
    host = _auth(client, "tz_host@example.com", "TZ Host")
    guest = _auth(client, "tz_guest@example.com", "TZ Guest")
    guest_id = client.get("/users/me", headers=guest).json()["data"]["id"]

    # Default timezone is UTC; the guest sets theirs to New York.
    me = client.get("/users/me", headers=guest).json()["data"]
    assert me["timezone"] == "UTC"
    upd = client.patch("/users/me", json={"timezone": "America/New_York"}, headers=guest)
    assert upd.status_code == 200 and upd.json()["data"]["timezone"] == "America/New_York"

    # A proposed session notifies the guest with the time in THEIR timezone.
    client.post(
        "/sessions",
        json={"partner_id": guest_id, "scheduled_at": "2099-06-01T18:00:00Z"},
        headers=host,
    )
    notes = client.get("/notifications", headers=guest).json()["data"]
    body = next(n["body"] for n in notes if n["type"] == "meetup")
    # 18:00 UTC on Jun 1 is 2:00 PM EDT — rendered with the EDT abbreviation.
    assert "EDT" in body and "2:00 PM" in body

    # An invalid timezone is tolerated (falls back to UTC formatting, no crash).
    client.patch("/users/me", json={"timezone": "Not/AZone"}, headers=guest)
    assert client.get("/users/me", headers=guest).json()["data"]["timezone"] == "Not/AZone"


def test_session_scheduling(client):
    host = _auth(client, "host@example.com", "Host")
    guest = _auth(client, "guest@example.com", "Guest")
    guest_id = client.get("/users/me", headers=guest).json()["data"]["id"]

    when = "2099-01-01T15:00:00Z"
    prop = client.post(
        "/sessions",
        json={"partner_id": guest_id, "scheduled_at": when, "skill": "Guitar", "is_trial": True},
        headers=host,
    )
    assert prop.status_code == 201
    s = prop.json()["data"]
    assert s["status"] == "proposed" and s["is_trial"] and s["duration_min"] == 15

    # It shows up for both parties.
    assert len(client.get("/sessions", headers=host).json()["data"]) == 1
    assert len(client.get("/sessions", headers=guest).json()["data"]) == 1

    # Only the guest can respond; confirming works.
    assert client.post(f"/sessions/{s['id']}/respond", json={"accept": True}, headers=host).status_code == 404
    conf = client.post(f"/sessions/{s['id']}/respond", json={"accept": True}, headers=guest)
    assert conf.status_code == 200 and conf.json()["data"]["status"] == "confirmed"

    # Past times and self-booking are rejected.
    assert client.post("/sessions", json={"partner_id": guest_id, "scheduled_at": "2000-01-01T00:00:00Z"}, headers=host).status_code == 400

    # Availability note round-trips through the profile.
    client.patch("/users/me", json={"availability_note": "Weekday evenings ET"}, headers=guest)
    prof = client.get(f"/users/{guest_id}/profile", headers=host).json()["data"]
    assert prof["availability_note"] == "Weekday evenings ET"


def test_flashcards_spaced_repetition(client):
    hdr = _auth(client, "cards@example.com", "Cards")
    gen = client.post("/flashcards/generate", json={"topic": "Python decorators"}, headers=hdr)
    assert gen.status_code == 201
    cards = gen.json()["data"]["cards"]
    assert len(cards) >= 2 and cards[0]["front"] and cards[0]["back"]

    # They're due today.
    due = client.get("/flashcards", headers=hdr).json()["data"]
    assert due["due_count"] == len(cards) and due["total"] == len(cards)

    # Reviewing "good" pushes the due date into the future (drops from due list).
    cid = cards[0]["id"]
    rev = client.post(f"/flashcards/{cid}/review", json={"grade": "good"}, headers=hdr)
    assert rev.status_code == 200 and rev.json()["data"]["interval_days"] >= 2
    after = client.get("/flashcards", headers=hdr).json()["data"]
    assert after["due_count"] == len(cards) - 1

    # Bad grade rejected; deleting works.
    assert client.post(f"/flashcards/{cid}/review", json={"grade": "meh"}, headers=hdr).status_code == 422
    assert client.delete(f"/flashcards/{cid}", headers=hdr).status_code == 200


def test_gamification_extras(client):
    hdr = _auth(client, "gamer@example.com", "Gamer")
    prog = client.get("/progress", headers=hdr).json()["data"]
    assert prog["daily_goal"] == 30 and prog["streak_freezes"] == 2 and "daily_goal_pct" in prog

    # Set + validate the daily goal.
    assert client.post("/progress/daily-goal", json={"xp": 50}, headers=hdr).json()["data"]["daily_goal"] == 50
    assert client.post("/progress/daily-goal", json={"xp": 5}, headers=hdr).status_code == 422

    # League standings for the user's (Bronze) division.
    lg = client.get("/league", headers=hdr).json()["data"]
    assert lg["division"] == "Bronze" and isinstance(lg["entries"], list)

    # A free user can't afford a freeze (needs 20 tokens); Elite gets it free.
    assert client.post("/progress/buy-freeze", headers=hdr).status_code == 402
    client.post("/billing/subscribe", json={"tier": "elite"}, headers=hdr)
    r = client.post("/progress/buy-freeze", headers=hdr)
    assert r.status_code == 200 and r.json()["data"]["streak_freezes"] == 3


def test_match_icebreakers(client):
    a = _auth(client, "ice_a@example.com", "Ice A")
    b = _auth(client, "ice_b@example.com", "Ice B")
    client.post("/skills", json={"name": "Guitar", "kind": "have"}, headers=b)
    client.post("/skills", json={"name": "Guitar", "kind": "want"}, headers=a)
    b_id = client.get("/users/me", headers=b).json()["data"]["id"]

    res = client.get(f"/matches/{b_id}/icebreakers", headers=a)
    assert res.status_code == 200
    openers = res.json()["data"]["icebreakers"]
    assert isinstance(openers, list) and len(openers) >= 2
    # Unknown partner 404s.
    assert client.get("/matches/999999/icebreakers", headers=a).status_code == 404


def test_message_reactions(client):
    a = _auth(client, "react_a@example.com", "React A")
    b = _auth(client, "react_b@example.com", "React B")
    b_id = client.get("/users/me", headers=b).json()["data"]["id"]
    msg = client.post(f"/messages/{b_id}", json={"body": "hey"}, headers=a).json()["data"]
    assert msg["reaction"] is None

    # B reacts to A's message.
    r = client.post(f"/messages/{msg['id']}/react", json={"emoji": "❤️"}, headers=b)
    assert r.status_code == 200 and r.json()["data"]["reaction"] == "❤️"
    # It shows up in the conversation.
    convo = client.get(f"/messages/{b_id}", headers=a).json()["data"]
    assert any(m["id"] == msg["id"] and m["reaction"] == "❤️" for m in convo["messages"])
    # Clearing works, and outsiders can't react.
    assert client.post(f"/messages/{msg['id']}/react", json={"emoji": None}, headers=b).json()["data"]["reaction"] is None
    outsider = _auth(client, "react_c@example.com", "React C")
    assert client.post(f"/messages/{msg['id']}/react", json={"emoji": "👍"}, headers=outsider).status_code == 404


def test_realtime_message_delivery(client):
    a = _auth(client, "rt_sender@example.com", "RT Sender")
    b = _auth(client, "rt_recipient@example.com", "RT Recipient")
    a_id = client.get("/users/me", headers=a).json()["data"]["id"]
    b_id = client.get("/users/me", headers=b).json()["data"]["id"]

    # B opens their personal socket (uid fallback works outside production).
    with client.websocket_connect(f"/ws/user?uid={b_id}") as ws:
        assert ws.receive_json()["type"] == "ready"
        # A messages B — B should receive a live "message" event.
        r = client.post(f"/messages/{b_id}", json={"body": "hi live"}, headers=a)
        assert r.status_code == 201
        evt = ws.receive_json()
        assert evt["type"] == "message"
        assert evt["data"]["body"] == "hi live"
        assert evt["data"]["from_id"] == a_id and evt["data"]["mine"] is False


def test_public_profile(client):
    hdr = _auth(client, "profileowner@example.com", "Profile Owner")
    client.post("/skills", json={"name": "Python", "kind": "have", "level": "advanced"}, headers=hdr)
    me = client.get("/users/me", headers=hdr).json()["data"]

    viewer = _auth(client, "profileviewer@example.com", "Viewer")
    prof = client.get(f"/users/{me['id']}/profile", headers=viewer)
    assert prof.status_code == 200
    data = prof.json()["data"]
    assert data["name"] == "Profile Owner"
    assert data["level"] >= 1 and "xp" in data
    assert any(s["name"] == "Python" for s in data["skills"])
    assert "badges" in data and "reputation" in data

    # Unknown user 404s.
    assert client.get("/users/999999/profile", headers=viewer).status_code == 404


def test_referral_bonus(client):
    inviter = _auth(client, "inviter@example.com", "Inviter")
    ref = client.get("/referrals/me", headers=inviter).json()["data"]
    code = ref["code"]
    assert code and ref["referred_count"] == 0 and ref["bonus_tokens"] == 200

    # A new user signs up with the code — both parties get bonus tokens.
    r = client.post(
        "/auth/signup",
        json={
            "email": "invitee@example.com",
            "password": "supersecret1",
            "name": "Invitee",
            "referral_code": code,
        },
    )
    assert r.status_code == 201
    invitee = {"Authorization": f"Bearer {r.json()['data']['token']}"}
    assert client.get("/billing/tokens", headers=invitee).json()["data"]["wallet"]["purchased"] == 200
    assert client.get("/billing/tokens", headers=inviter).json()["data"]["wallet"]["purchased"] == 200
    assert client.get("/referrals/me", headers=inviter).json()["data"]["referred_count"] == 1

    # An invalid code is ignored — signup still succeeds, no bonus granted.
    r2 = client.post(
        "/auth/signup",
        json={"email": "noref@example.com", "password": "supersecret1", "referral_code": "BADCODE9"},
    )
    assert r2.status_code == 201
    noref = {"Authorization": f"Bearer {r2.json()['data']['token']}"}
    assert client.get("/billing/tokens", headers=noref).json()["data"]["wallet"]["purchased"] == 0


def test_password_reset_flow(client):
    email = "resetme@example.com"
    client.post("/auth/signup", json={"email": email, "password": "originalpass1", "name": "R"})

    # Forgot for an unknown email still returns 200 (no account enumeration).
    assert client.post("/auth/forgot-password", json={"email": "nobody@example.com"}).status_code == 200

    reset_token = client.post("/auth/forgot-password", json={"email": email}).json()["data"]["dev_token"]
    # Reset the password.
    assert client.post("/auth/reset-password", json={"token": reset_token, "password": "brandnewpass2"}).status_code == 200
    # Old password no longer works; new one does.
    assert client.post("/auth/login", json={"email": email, "password": "originalpass1"}).status_code == 401
    assert client.post("/auth/login", json={"email": email, "password": "brandnewpass2"}).status_code == 200


def test_delete_account(client):
    hdr = _auth(client, "deleteme@example.com", "Delete Me")
    # Add some data that should cascade away.
    client.post("/skills", json={"name": "Rust", "kind": "have"}, headers=hdr)
    assert client.delete("/users/me", headers=hdr).status_code == 200
    # The token no longer resolves to a user.
    assert client.get("/users/me", headers=hdr).status_code == 401
    # Re-signup with the same email now succeeds (account is gone).
    assert client.post(
        "/auth/signup", json={"email": "deleteme@example.com", "password": "supersecret123"}
    ).status_code == 201


def test_block_hides_from_matches_and_messages(client):
    ana = _auth(client, "blkana@example.com", "Blk Ana")
    ben = _auth(client, "blkben@example.com", "Blk Ben")
    ana_id = client.get("/users/me", headers=ana).json()["data"]["id"]
    ben_id = client.get("/users/me", headers=ben).json()["data"]["id"]

    client.post("/skills", json={"name": "Python", "kind": "have"}, headers=ana)
    client.post("/skills", json={"name": "Guitar", "kind": "want"}, headers=ana)
    client.post("/skills", json={"name": "Guitar", "kind": "have"}, headers=ben)
    client.post("/skills", json={"name": "Python", "kind": "want"}, headers=ben)

    assert any(m["user_id"] == ben_id for m in client.get("/matches", headers=ana).json()["data"])

    # Ana blocks Ben.
    assert client.post(f"/blocks/{ben_id}", headers=ana).status_code == 200
    # Ben vanishes from Ana's matches AND Ana from Ben's (block is mutual in effect).
    assert all(m["user_id"] != ben_id for m in client.get("/matches", headers=ana).json()["data"])
    assert all(m["user_id"] != ana_id for m in client.get("/matches", headers=ben).json()["data"])
    # Neither can message the other.
    assert client.post(f"/messages/{ben_id}", json={"body": "hi"}, headers=ana).status_code == 403
    assert client.post(f"/messages/{ana_id}", json={"body": "hi"}, headers=ben).status_code == 403

    # Blocked list shows Ben; unblocking restores matches + messaging.
    assert client.get("/blocks", headers=ana).json()["data"][0]["user_id"] == ben_id
    assert client.delete(f"/blocks/{ben_id}", headers=ana).status_code == 200
    assert any(m["user_id"] == ben_id for m in client.get("/matches", headers=ana).json()["data"])
    assert client.post(f"/messages/{ben_id}", json={"body": "hi again"}, headers=ana).status_code == 201

    # Can't block yourself / unknown user.
    assert client.post(f"/blocks/{ana_id}", headers=ana).status_code == 400
    assert client.post("/blocks/999999", headers=ana).status_code == 404


def test_report_content(client):
    hdr = _auth(client, "reporter@example.com", "Reporter")
    assert client.post("/reports", json={"target_type": "post", "target_id": 1, "reason": "spam"}, headers=hdr).status_code == 201
    assert client.post("/reports", json={"target_type": "user", "target_id": 2, "reason": "abuse"}, headers=hdr).status_code == 201
    # Invalid target type rejected.
    assert client.post("/reports", json={"target_type": "banana", "target_id": 1, "reason": "x"}, headers=hdr).status_code == 422


def test_moderator_dashboard(client):
    mod = _auth(client, "mod@example.com", "Mod")       # admin (ADMIN_EMAILS)
    user = _auth(client, "reguser@example.com", "Reg")  # non-admin

    # is_admin flag is exposed on the user object.
    assert client.get("/users/me", headers=mod).json()["data"]["is_admin"] is True
    assert client.get("/users/me", headers=user).json()["data"]["is_admin"] is False

    # A user files a report.
    client.post("/reports", json={"target_type": "user", "target_id": 1, "reason": "spam"}, headers=user)

    # Non-admin can't reach the dashboard.
    assert client.get("/admin/reports", headers=user).status_code == 403

    # Admin sees the open report and can resolve it.
    reports = client.get("/admin/reports", headers=mod).json()["data"]
    assert len(reports) >= 1 and reports[0]["status"] == "open"
    rid = reports[0]["id"]
    assert client.post(f"/admin/reports/{rid}/resolve", headers=mod).status_code == 200
    # It drops out of the default (open) view.
    assert all(r["id"] != rid for r in client.get("/admin/reports", headers=mod).json()["data"])
    # But shows in the 'all' view as reviewed.
    all_reports = client.get("/admin/reports?status=all", headers=mod).json()["data"]
    assert any(r["id"] == rid and r["status"] == "reviewed" for r in all_reports)


def test_academy_catalog_enroll_and_progress(client):
    hdr = _auth(client, "learner1@example.com", "Learner One")
    client.post("/billing/subscribe", json={"tier": "pro"}, headers=hdr)  # Academy is Pro

    # A large, diverse catalog is served.
    cats = client.get("/academy/categories", headers=hdr).json()["data"]
    assert "All" in cats and len(cats) >= 6
    paths = client.get("/academy/paths", headers=hdr).json()
    assert paths["meta"]["total"] >= 20
    slug = paths["data"][0]["slug"]
    assert paths["data"][0]["enrolled"] is False

    # Category filter narrows results.
    prog_cat = "Programming"
    filtered = client.get(f"/academy/paths?category={prog_cat}", headers=hdr).json()["data"]
    assert filtered and all(p["category"] == prog_cat for p in filtered)

    # Before enrolling, only the preview lesson is unlocked.
    detail = client.get(f"/academy/paths/{slug}", headers=hdr).json()["data"]
    all_lessons = [l for m in detail["modules"] for l in m["lessons"]]
    assert all_lessons[0]["locked"] is False and "steps" in all_lessons[0]
    assert all_lessons[-1]["locked"] is True and "steps" not in all_lessons[-1]

    # Completing a lesson before enrolling is blocked.
    first_key = all_lessons[0]["key"]
    assert client.post(f"/academy/paths/{slug}/lessons/{first_key}/complete", headers=hdr).status_code == 403

    # Enroll -> everything unlocks.
    assert client.post(f"/academy/paths/{slug}/enroll", headers=hdr).status_code == 201
    detail2 = client.get(f"/academy/paths/{slug}", headers=hdr).json()["data"]
    assert detail2["enrolled"] is True
    assert all(not l["locked"] for m in detail2["modules"] for l in m["lessons"])

    # Complete a lesson -> progress + XP.
    r = client.post(f"/academy/paths/{slug}/lessons/{first_key}/complete", headers=hdr).json()["data"]
    assert r["completed"] == 1 and r["progress"] > 0 and r["xp"] >= 15
    # Idempotent (no double XP).
    again = client.post(f"/academy/paths/{slug}/lessons/{first_key}/complete", headers=hdr).json()["data"]
    assert again["completed"] == 1

    # Unknown lesson / path guardrails.
    assert client.post(f"/academy/paths/{slug}/lessons/zzz/complete", headers=hdr).status_code == 404
    assert client.get("/academy/paths/does-not-exist", headers=hdr).status_code == 404


def test_academy_lesson_content(client):
    hdr = _auth(client, "learner3@example.com", "Learner Three")
    paths = client.get("/academy/paths", headers=hdr).json()["data"]
    slug = paths[0]["slug"]
    detail = client.get(f"/academy/paths/{slug}", headers=hdr).json()["data"]
    lessons = [l for m in detail["modules"] for l in m["lessons"]]
    first_key, last_key = lessons[0]["key"], lessons[-1]["key"]

    # Preview lesson: taught content is available (article + resources).
    r = client.get(f"/academy/paths/{slug}/lessons/{first_key}/content", headers=hdr)
    assert r.status_code == 200
    data = r.json()["data"]
    assert isinstance(data["article"], str) and len(data["article"]) > 80
    res = data["resources"]
    assert res["video_url"].startswith("https://www.youtube.com/") and res["read_url"].startswith("http")
    assert data["steps"] and data["exercise"]

    # A locked lesson's content requires enrollment.
    assert client.get(f"/academy/paths/{slug}/lessons/{last_key}/content", headers=hdr).status_code == 403
    # After upgrading (Academy is Pro) and enrolling, it's available.
    client.post("/billing/subscribe", json={"tier": "pro"}, headers=hdr)
    client.post(f"/academy/paths/{slug}/enroll", headers=hdr)
    assert client.get(f"/academy/paths/{slug}/lessons/{last_key}/content", headers=hdr).status_code == 200


def test_academy_ai_tutor_fallback(client):
    hdr = _auth(client, "learner2@example.com", "Learner Two")
    paths = client.get("/academy/paths", headers=hdr).json()["data"]
    slug = paths[0]["slug"]
    first_key = client.get(f"/academy/paths/{slug}", headers=hdr).json()["data"]["modules"][0]["lessons"][0]["key"]

    # Preview lesson: AI tutor works (Groq unconfigured -> graceful fallback).
    r = client.post(
        f"/academy/paths/{slug}/lessons/{first_key}/assist",
        json={"mode": "explain"},
        headers=hdr,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["mode"] == "explain" and isinstance(data["answer"], str) and data["answer"]

    # A locked lesson's tutor requires enrollment.
    last_key = client.get(f"/academy/paths/{slug}", headers=hdr).json()["data"]["modules"][-1]["lessons"][-1]["key"]
    assert client.post(
        f"/academy/paths/{slug}/lessons/{last_key}/assist", json={"mode": "hint"}, headers=hdr
    ).status_code == 403


def test_billing_plans_and_subscribe(client):
    hdr = _auth(client, "tierbob@example.com", "Tier Bob")
    plans = client.get("/billing/plans", headers=hdr).json()["data"]
    assert [p["tier"] for p in plans["plans"]] == ["free", "pro", "elite"]
    assert plans["current"] == "free"
    assert client.get("/users/me", headers=hdr).json()["data"]["tier"] == "free"

    # Upgrade to Pro.
    assert client.post("/billing/subscribe", json={"tier": "pro"}, headers=hdr).status_code == 200
    me = client.get("/billing/me", headers=hdr).json()["data"]
    assert me["tier"] == "pro" and me["tokens"]["allowance"] == 2000
    assert client.get("/users/me", headers=hdr).json()["data"]["tier"] == "pro"
    # Cancel back to free.
    client.post("/billing/subscribe", json={"tier": "free"}, headers=hdr)
    assert client.get("/users/me", headers=hdr).json()["data"]["tier"] == "free"
    # Invalid tier rejected.
    assert client.post("/billing/subscribe", json={"tier": "platinum"}, headers=hdr).status_code == 422


def test_tier_feature_gating(client):
    hdr = _auth(client, "gateuser@example.com", "Gate User")

    def blocked(method, path, **kw):
        r = getattr(client, method)(path, headers=hdr, **kw)
        return r.status_code == 402

    # Free tier: paid features are blocked with 402.
    assert blocked("post", "/rooms", json={"title": "Room"})
    assert blocked("post", "/twin/1/chat", json={"message": "hi"})
    assert blocked("post", "/twin/train", json={"samples": "x" * 30})
    assert blocked("post", "/verifications", json={"skill_name": "Python"})
    assert blocked("post", "/resume/build", json={"name": "Gate User", "target_role": "Engineer", "skills": ["Python"]})

    # Upgrade to Pro: rooms + career unlock; twin-train + verification still need Elite.
    client.post("/billing/subscribe", json={"tier": "pro"}, headers=hdr)
    assert client.post("/rooms", json={"title": "Room"}, headers=hdr).status_code == 201
    assert not blocked("post", "/twin/1/chat", json={"message": "hi"})  # not 402 anymore
    assert blocked("post", "/twin/train", json={"samples": "x" * 30})
    assert blocked("post", "/verifications", json={"skill_name": "Python"})

    # Upgrade to Elite: everything unlocks.
    client.post("/billing/subscribe", json={"tier": "elite"}, headers=hdr)
    assert not blocked("post", "/twin/train", json={"samples": "x" * 30})
    assert not blocked("post", "/verifications", json={"skill_name": "Python"})


def test_free_ai_token_allowance(client):
    hdr = _auth(client, "quotauser@example.com", "Quota User")
    body = {"text": "hello world", "target_language": "Spanish"}

    # Free tier: 3 monthly AI tokens (test override), 1 per action, then 402.
    tokens = client.get("/billing/tokens", headers=hdr).json()["data"]
    assert tokens["wallet"]["balance"] == 3
    assert [p["id"] for p in tokens["packs"]] == ["small", "medium", "large"]
    for _ in range(3):
        assert client.post("/translate", json=body, headers=hdr).status_code == 200
    assert client.post("/translate", json=body, headers=hdr).status_code == 402
    wallet = client.get("/billing/tokens", headers=hdr).json()["data"]["wallet"]
    assert wallet["allowance_remaining"] == 0 and wallet["balance"] == 0

    # Buy a top-up pack — the purchased tokens restore access.
    buy = client.post("/billing/tokens/buy", json={"pack": "small"}, headers=hdr)
    assert buy.status_code == 200
    assert buy.json()["data"]["wallet"]["purchased"] == 500
    assert client.post("/translate", json=body, headers=hdr).status_code == 200
    wallet = client.get("/billing/tokens", headers=hdr).json()["data"]["wallet"]
    assert wallet["purchased"] == 499  # allowance was empty, so it drew from top-up

    # Unknown pack is rejected.
    assert client.post("/billing/tokens/buy", json={"pack": "mega"}, headers=hdr).status_code == 422


def test_elite_ai_tokens_unlimited(client):
    hdr = _auth(client, "eliteai@example.com", "Elite AI")
    client.post("/billing/subscribe", json={"tier": "elite"}, headers=hdr)
    body = {"text": "hello world", "target_language": "Spanish"}
    for _ in range(5):
        assert client.post("/translate", json=body, headers=hdr).status_code == 200
    wallet = client.get("/billing/tokens", headers=hdr).json()["data"]["wallet"]
    assert wallet["unlimited"] is True and wallet["balance"] is None


def test_admin_is_elite_tier(client):
    admin = _auth(client, "elite-admin@example.com", "Elite Admin")  # in ADMIN_EMAILS
    assert client.get("/billing/me", headers=admin).json()["data"]["tier"] == "elite"
    # Admin can use an Elite-gated feature.
    assert client.post("/verifications", json={"skill_name": "Python"}, headers=admin).status_code in (200, 201)


def test_missing_auth_returns_envelope(client):
    r = client.post("/roadmap", json={"goal": "x", "current_skills": []})
    assert r.status_code == 401
    _assert_envelope(r.json())
    assert r.json()["success"] is False
