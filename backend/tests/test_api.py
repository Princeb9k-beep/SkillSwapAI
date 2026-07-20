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


def test_skill_verification_peer_review(client):
    owner = _auth(client, "vera@example.com", "Vera")
    r1 = _auth(client, "rob@example.com", "Rob")
    r2 = _auth(client, "sue@example.com", "Sue")

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
    uid = client.get("/users/me", headers=host).json()["data"]["id"]
    code = client.post("/rooms", json={"title": "Pairing"}, headers=host).json()["data"]["code"]

    # The signaling socket greets a peer with a welcome + the current peer list.
    with client.websocket_connect(f"/rooms/ws/{code}?uid={uid}") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "welcome"
        assert isinstance(hello["peers"], list) and "peer_id" in hello


def test_practice_room_signaling_rejects_unauthenticated(client):
    host = _auth(client, "sig2@example.com", "Sig Two")
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


def test_missing_auth_returns_envelope(client):
    r = client.post("/roadmap", json={"goal": "x", "current_skills": []})
    assert r.status_code == 401
    _assert_envelope(r.json())
    assert r.json()["success"] is False
