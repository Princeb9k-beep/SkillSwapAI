"""Session issuing + refresh-token management.

Centralizes how a signed-in session is minted (access token + a stored,
revocable refresh token) so signup, login, and OAuth all behave identically.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import (
    REFRESH_TTL,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from .deps import user_is_admin
from .models import RefreshToken, User
from .schemas import UserOut


def _aware(dt: datetime) -> datetime:
    """Treat a naive datetime (as SQLite returns) as UTC for safe comparison."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _user_payload(user: User) -> dict:
    data = UserOut.model_validate(user).model_dump(mode="json")
    data["is_admin"] = user_is_admin(user)
    return data


async def issue_session(
    session: AsyncSession, user: User, user_agent: str | None = None, *, extra: dict | None = None
) -> dict:
    """Create a refresh token and return the auth payload (access + refresh + user)."""
    raw, token_hash = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            user_agent=(user_agent or "")[:255] or None,
            expires_at=datetime.now(timezone.utc) + REFRESH_TTL,
        )
    )
    await session.commit()
    payload = {
        "token": create_access_token(user.id),
        "refresh_token": raw,
        "user": _user_payload(user),
    }
    if extra:
        payload.update(extra)
    return payload


async def rotate_refresh_token(
    session: AsyncSession, raw: str, user_agent: str | None = None
) -> dict | None:
    """Validate a refresh token, revoke it, and mint a fresh session. None if invalid."""
    token_hash = hash_refresh_token(raw)
    row = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is None or row.revoked or _aware(row.expires_at) <= now:
        return None
    user = await session.get(User, row.user_id)
    if user is None:
        return None
    row.revoked = True  # rotation: single-use refresh tokens
    await session.commit()
    return await issue_session(session, user, user_agent)


async def revoke_refresh_token(session: AsyncSession, raw: str) -> None:
    token_hash = hash_refresh_token(raw)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .values(revoked=True)
    )
    await session.commit()


async def revoke_all_for_user(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    await session.commit()
    return result.rowcount or 0


async def active_session_count(session: AsyncSession, user_id: int) -> int:
    now = datetime.now(timezone.utc)
    rows = (
        await session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > now,
            )
        )
    ).scalars().all()
    return len(rows)
