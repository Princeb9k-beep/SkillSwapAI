"""In-process per-user WebSocket hub for live updates.

Each signed-in browser tab opens one personal WebSocket (`/ws/user`). Anything
that wants to nudge a user in real time — a new message, a fresh notification —
calls ``hub.send_to_user(user_id, payload)`` and every open tab for that user
receives it.

This is process-local (like the video-room manager). It's the right fit for the
single web service the app deploys as; scaling to multiple instances would swap
this for Redis pub/sub behind the same interface.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger("skillswap.realtime")


class UserHub:
    def __init__(self) -> None:
        self._peers: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._peers.setdefault(user_id, set()).add(ws)

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._peers.get(user_id)
            if conns:
                conns.discard(ws)
                if not conns:
                    self._peers.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: dict) -> None:
        """Fan a payload out to every open tab for a user. Never raises."""
        conns = list(self._peers.get(user_id, ()))
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception as exc:  # noqa: BLE001 — drop dead sockets
                logger.debug("realtime send failed for user %s: %s", user_id, exc)
                await self.disconnect(user_id, ws)

    def is_online(self, user_id: int) -> bool:
        return bool(self._peers.get(user_id))

    def online_ids(self) -> set[int]:
        return {uid for uid, conns in self._peers.items() if conns}

    async def broadcast(self, payload: dict, exclude: int | None = None) -> None:
        """Send a payload to every connected user (small-scale presence fan-out)."""
        for uid in list(self._peers.keys()):
            if uid == exclude:
                continue
            await self.send_to_user(uid, payload)


hub = UserHub()
