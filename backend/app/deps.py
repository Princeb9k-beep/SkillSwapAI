"""
Shared FastAPI dependencies.

Authentication is JWT-based: clients send `Authorization: Bearer <token>` obtained
from /auth/signup or /auth/login. For local dev/tests (any non-production
APP_ENV) an `X-User-Id` header is also accepted as a convenience fallback; in
production only a valid Bearer token is honored.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import decode_access_token
from .config import get_settings
from .database import get_session
from .models import User

_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Please sign in to continue.",
)


async def get_current_user(
    authorization: str | None = Header(default=None),
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Resolve the acting user from a Bearer JWT (or X-User-Id in dev)."""
    user_id: int | None = None

    if authorization and authorization.lower().startswith("bearer "):
        user_id = decode_access_token(authorization[7:].strip())

    if user_id is None and x_user_id is not None:
        # Dev/test convenience only — disabled in production.
        if get_settings().app_env != "production":
            user_id = x_user_id

    if user_id is None:
        raise _UNAUTH

    user = await session.get(User, user_id)
    if user is None:
        raise _UNAUTH
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


def user_is_admin(user: User) -> bool:
    """A user is a moderator/admin if their email is in ADMIN_EMAILS."""
    return bool(user.email) and user.email.lower() in get_settings().admin_email_set


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that allows only moderators/admins."""
    if not user_is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Moderator access required."
        )
    return user
