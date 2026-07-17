"""
Shared FastAPI dependencies.

Auth is intentionally **stubbed** for this version: the caller identifies itself
with an `X-User-Id` header. If the id doesn't exist yet we create a placeholder
user row so the AI features work end-to-end. Swapping this for real JWT auth later
only touches this file plus the users router (password_hash is already scaffolded
on the model).
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_session
from .models import User


async def get_current_user(
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Resolve the acting user from the X-User-Id header (stubbed auth)."""
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header. Create a user via POST /users first.",
        )
    user = await session.get(User, x_user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {x_user_id} not found. Create one via POST /users.",
        )
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
