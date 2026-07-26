"""Personal WebSocket endpoint for live updates (messages, notifications).

Authenticated from the `token` query param (browsers can't set WS headers),
with a dev-only `uid` fallback. Keeps the socket open, replies to pings, and
relies on app code calling `hub.send_to_user(...)` to push events.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..auth import decode_access_token
from ..config import get_settings
from ..realtime import hub

router = APIRouter(tags=["realtime"])


def _resolve_user_id(websocket: WebSocket) -> int | None:
    token = websocket.query_params.get("token")
    if token:
        uid = decode_access_token(token)
        if uid is not None:
            return uid
    if get_settings().app_env != "production":
        uid = websocket.query_params.get("uid")
        if uid and uid.isdigit():
            return int(uid)
    return None


@router.websocket("/ws/user")
async def user_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    user_id = _resolve_user_id(websocket)
    if user_id is None:
        await websocket.send_json({"type": "error", "message": "unauthorized"})
        await websocket.close(code=4401)
        return

    await hub.connect(user_id, websocket)
    await websocket.send_json({"type": "ready"})
    try:
        while True:
            # We don't need inbound data; this also answers client pings and
            # detects disconnects.
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(user_id, websocket)
