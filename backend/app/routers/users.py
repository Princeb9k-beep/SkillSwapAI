"""User endpoints (stubbed auth: upsert by email, then use id in X-User-Id)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user, get_user_by_email
from ..models import User
from ..responses import ok
from ..schemas import UserOut, UserUpsert

router = APIRouter(prefix="/users", tags=["users"])


@router.post("")
async def upsert_user(
    payload: UserUpsert, session: AsyncSession = Depends(get_session)
) -> object:
    """
    Create or update a user by email. Returns the user (including the id to pass as
    the `X-User-Id` header on subsequent calls).
    """
    user = await get_user_by_email(session, payload.email)
    if user is None:
        user = User(email=payload.email)
        session.add(user)
    user.name = payload.name if payload.name is not None else user.name
    user.goal = payload.goal if payload.goal is not None else user.goal
    if payload.target_income is not None:
        user.target_income = payload.target_income
    await session.commit()
    await session.refresh(user)
    return ok(data=UserOut.model_validate(user).model_dump(mode="json"),
              message="User saved")


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> object:
    """Return the current (header-identified) user."""
    return ok(data=UserOut.model_validate(user).model_dump(mode="json"))
