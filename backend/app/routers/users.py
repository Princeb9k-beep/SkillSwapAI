"""User profile endpoints (authenticated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import User
from ..responses import ok
from ..schemas import ProfileUpdate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> object:
    """Return the current (token-identified) user."""
    return ok(data=UserOut.model_validate(user).model_dump(mode="json"))


@router.patch("/me")
async def update_me(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Update the current user's name / goal / target income."""
    if payload.name is not None:
        user.name = payload.name
    if payload.goal is not None:
        user.goal = payload.goal
    if payload.target_income is not None:
        user.target_income = payload.target_income
    await session.commit()
    return ok(
        data=UserOut.model_validate(user).model_dump(mode="json"),
        message="Profile updated",
    )
