"""Video practice rooms (spec §2.3).

Real-time peer-to-peer video/screen-share/whiteboard runs over **WebRTC** in the
browser; the backend's job is (1) a REST lobby to create/list/join/close rooms and
persist shared notes, and (2) a **WebSocket signaling relay** that brokers the WebRTC
offer/answer/ICE handshake between peers and fans out chat + presence.

The relay keeps an in-process registry of live connections per room. That is correct
for a single web instance (our Render deploy). Scaling to multiple instances would
require a shared pub/sub fabric (e.g. Redis) behind the relay, and reliable media
across restrictive NATs needs a TURN server — both are noted as production follow-ups.
"""

from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import decode_access_token
from ..config import get_settings
from ..database import get_session, get_sessionmaker
from ..deps import get_current_user
from ..models import PracticeRoom, RoomParticipant, User
from ..plans import has_feature, require_feature
from ..responses import error, ok
from ..schemas import RoomCreate, RoomNotesUpdate

router = APIRouter(prefix="/rooms", tags=["rooms"])


def _new_code() -> str:
    """A short, URL-safe, hard-to-guess join code."""
    return secrets.token_urlsafe(6)[:8]


def _room_dict(room: PracticeRoom, live: int, host_name: str | None) -> dict:
    return {
        "id": room.id,
        "code": room.code,
        "title": room.title,
        "topic": room.topic,
        "host_id": room.host_id,
        "host_name": host_name or f"Learner #{room.host_id}",
        "is_open": room.is_open,
        "live_count": live,
        "created_at": room.created_at.isoformat() if room.created_at else None,
    }


# --------------------------------------------------------------------------- #
# In-memory signaling relay
# --------------------------------------------------------------------------- #
class _Connection:
    __slots__ = ("ws", "peer_id", "user_id", "name")

    def __init__(self, ws: WebSocket, peer_id: str, user_id: int, name: str):
        self.ws = ws
        self.peer_id = peer_id
        self.user_id = user_id
        self.name = name


class SignalingHub:
    """Tracks live WebSocket peers per room code and relays messages between them."""

    def __init__(self) -> None:
        self._rooms: dict[str, dict[str, _Connection]] = defaultdict(dict)

    def peers(self, code: str) -> list[_Connection]:
        return list(self._rooms.get(code, {}).values())

    def live_count(self, code: str) -> int:
        return len(self._rooms.get(code, {}))

    def add(self, code: str, conn: _Connection) -> None:
        self._rooms[code][conn.peer_id] = conn

    def remove(self, code: str, peer_id: str) -> None:
        room = self._rooms.get(code)
        if room:
            room.pop(peer_id, None)
            if not room:
                self._rooms.pop(code, None)

    async def send(self, conn: _Connection, message: dict) -> None:
        try:
            await conn.ws.send_json(message)
        except Exception:
            pass

    async def broadcast(self, code: str, message: dict, exclude: str | None = None) -> None:
        for conn in self.peers(code):
            if conn.peer_id != exclude:
                await self.send(conn, message)


hub = SignalingHub()


# --------------------------------------------------------------------------- #
# REST lobby
# --------------------------------------------------------------------------- #
@router.get("")
async def list_rooms(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """List open rooms (newest first) with their live participant counts."""
    rows = await session.execute(
        select(PracticeRoom, User.name)
        .join(User, User.id == PracticeRoom.host_id)
        .where(PracticeRoom.is_open.is_(True))
        .order_by(PracticeRoom.created_at.desc())
        .limit(50)
    )
    data = [
        _room_dict(room, hub.live_count(room.code), host_name)
        for room, host_name in rows.all()
    ]
    return ok(data=data)


@router.post("", dependencies=[Depends(require_feature("video_rooms"))])
async def create_room(
    payload: RoomCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Open a new practice room; the creator is the host (Pro+ only)."""
    # Retry on the (astronomically unlikely) code collision.
    code = _new_code()
    for _ in range(5):
        exists = await session.execute(
            select(PracticeRoom.id).where(PracticeRoom.code == code)
        )
        if exists.scalar_one_or_none() is None:
            break
        code = _new_code()

    room = PracticeRoom(
        code=code,
        title=payload.title.strip(),
        topic=payload.topic.strip() or "General",
        host_id=user.id,
    )
    session.add(room)
    await session.commit()
    return ok(
        data=_room_dict(room, 0, user.name),
        message="Room created",
        status_code=201,
    )


@router.get("/{code}")
async def get_room(
    code: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Room detail (used when joining) including shared notes and live count."""
    row = await session.execute(
        select(PracticeRoom, User.name)
        .join(User, User.id == PracticeRoom.host_id)
        .where(PracticeRoom.code == code)
    )
    found = row.first()
    if found is None:
        return error("Room not found.", status_code=404, code="not_found")
    room, host_name = found
    data = _room_dict(room, hub.live_count(room.code), host_name)
    data["notes"] = room.notes or ""
    return ok(data=data)


@router.put("/{code}/notes")
async def save_notes(
    code: str,
    payload: RoomNotesUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Persist the shared scratchpad so notes survive after the call ends."""
    room = (
        await session.execute(select(PracticeRoom).where(PracticeRoom.code == code))
    ).scalar_one_or_none()
    if room is None:
        return error("Room not found.", status_code=404, code="not_found")
    room.notes = payload.notes
    await session.commit()
    return ok(message="Notes saved")


@router.post("/{code}/close")
async def close_room(
    code: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Close a room (host only) so it drops out of the lobby."""
    room = (
        await session.execute(select(PracticeRoom).where(PracticeRoom.code == code))
    ).scalar_one_or_none()
    if room is None:
        return error("Room not found.", status_code=404, code="not_found")
    if room.host_id != user.id:
        return error("Only the host can close this room.", status_code=403, code="forbidden")
    room.is_open = False
    room.closed_at = datetime.now(timezone.utc)
    await session.commit()
    return ok(message="Room closed")


# --------------------------------------------------------------------------- #
# WebSocket signaling endpoint
# --------------------------------------------------------------------------- #
async def _resolve_ws_user(websocket: WebSocket, session: AsyncSession) -> User | None:
    """Authenticate a WebSocket from the `token` query param (JWT), with an
    `X-User-Id`-style `uid` fallback outside production (browsers can't set WS headers)."""
    user_id: int | None = None
    token = websocket.query_params.get("token")
    if token:
        user_id = decode_access_token(token)
    if user_id is None and get_settings().app_env != "production":
        uid = websocket.query_params.get("uid")
        if uid and uid.isdigit():
            user_id = int(uid)
    if user_id is None:
        return None
    return await session.get(User, user_id)


@router.websocket("/ws/{code}")
async def signaling(websocket: WebSocket, code: str) -> None:
    """WebRTC signaling relay for one room. Peers exchange SDP/ICE through here and
    then stream media directly to each other; chat and presence are also fanned out."""
    await websocket.accept()

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        user = await _resolve_ws_user(websocket, session)
        if user is None:
            await websocket.send_json({"type": "error", "message": "unauthorized"})
            await websocket.close(code=4401)
            return
        if not has_feature(user, "video_rooms"):
            await websocket.send_json(
                {"type": "error", "message": "Upgrade to Pro to join video rooms."}
            )
            await websocket.close(code=4403)
            return
        room = (
            await session.execute(select(PracticeRoom).where(PracticeRoom.code == code))
        ).scalar_one_or_none()
        if room is None or not room.is_open:
            await websocket.send_json({"type": "error", "message": "room unavailable"})
            await websocket.close(code=4404)
            return
        display_name = user.name or f"Learner #{user.id}"
        session.add(RoomParticipant(room_id=room.id, user_id=user.id))
        await session.commit()

    # Unique per connection (a user may open two tabs) so signaling addresses one socket.
    peer_id = secrets.token_urlsafe(6)
    conn = _Connection(websocket, peer_id, user.id, display_name)

    # Tell the newcomer who's already here, then announce them to the room.
    existing = [
        {"peer_id": c.peer_id, "user_id": c.user_id, "name": c.name}
        for c in hub.peers(code)
    ]
    hub.add(code, conn)
    await hub.send(conn, {"type": "welcome", "peer_id": peer_id, "peers": existing})
    await hub.broadcast(
        code,
        {"type": "peer-joined", "peer_id": peer_id, "user_id": user.id, "name": display_name},
        exclude=peer_id,
    )

    try:
        while True:
            msg = await websocket.receive_json()
            kind = msg.get("type")
            if kind == "signal":
                # Directed WebRTC handshake: forward SDP/ICE to one target peer.
                target = msg.get("to")
                dest = hub._rooms.get(code, {}).get(target)
                if dest is not None:
                    await hub.send(
                        dest,
                        {"type": "signal", "from": peer_id, "data": msg.get("data")},
                    )
            elif kind == "chat":
                text = str(msg.get("text", ""))[:2000]
                if text.strip():
                    await hub.broadcast(
                        code,
                        {"type": "chat", "from": peer_id, "name": display_name, "text": text},
                    )
            elif kind == "notes":
                # Live-share the whiteboard/notes text to co-participants.
                await hub.broadcast(
                    code,
                    {"type": "notes", "from": peer_id, "text": str(msg.get("text", ""))[:20000]},
                    exclude=peer_id,
                )
            # Unknown message types are ignored (forward-compatible).
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        hub.remove(code, peer_id)
        await hub.broadcast(code, {"type": "peer-left", "peer_id": peer_id})
        # Best-effort: stamp the participant's leave time.
        try:
            async with get_sessionmaker()() as session:
                row = await session.execute(
                    select(RoomParticipant)
                    .where(
                        RoomParticipant.user_id == conn.user_id,
                        RoomParticipant.left_at.is_(None),
                    )
                    .order_by(RoomParticipant.id.desc())
                    .limit(1)
                )
                participant = row.scalar_one_or_none()
                if participant is not None:
                    participant.left_at = datetime.now(timezone.utc)
                    await session.commit()
        except Exception:
            pass
