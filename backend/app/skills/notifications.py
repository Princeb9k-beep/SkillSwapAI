"""Notification creation helper (spec: real in-app notifications).

`create_notification` adds a Notification row without committing, so it composes
inside an endpoint's transaction (same pattern as gamification). Callers commit.
"""

from __future__ import annotations

from ..models import Notification


def create_notification(
    session,
    user_id: int,
    *,
    type: str = "system",
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> Notification:
    """Queue an in-app notification for a user (no commit)."""
    note = Notification(
        user_id=user_id,
        type=type,
        title=title[:160],
        body=(body[:500] if body else None),
        link=link,
    )
    session.add(note)
    return note
