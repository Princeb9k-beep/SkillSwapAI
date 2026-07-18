"""Authentication endpoints: signup and login."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import create_access_token, hash_password, verify_password
from ..database import get_session
from ..deps import get_user_by_email
from ..models import User
from ..responses import error, ok
from ..schemas import LoginRequest, SignupRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_payload(user: User) -> dict:
    return {
        "token": create_access_token(user.id),
        "user": UserOut.model_validate(user).model_dump(mode="json"),
    }


@router.post("/signup")
async def signup(
    payload: SignupRequest, session: AsyncSession = Depends(get_session)
) -> object:
    """Register a new account and return an access token."""
    existing = await get_user_by_email(session, payload.email)
    if existing is not None:
        return error(
            "An account with this email already exists. Try signing in.",
            status_code=409,
            code="email_taken",
        )
    user = User(
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)  # need created_at for UserOut
    return ok(data=_auth_payload(user), message="Account created", status_code=201)


@router.post("/login")
async def login(
    payload: LoginRequest, session: AsyncSession = Depends(get_session)
) -> object:
    """Authenticate and return an access token."""
    user = await get_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        return error(
            "Incorrect email or password.", status_code=401, code="bad_credentials"
        )
    return ok(data=_auth_payload(user), message="Signed in")
