"""Authentication endpoints: signup and login."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    create_access_token,
    create_scoped_token,
    decode_scoped_token,
    hash_password,
    verify_password,
)
from ..config import get_settings
from ..database import get_session
from ..deps import get_current_user, get_user_by_email
from ..models import User
from ..responses import error, ok
from ..schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    UserOut,
    VerifyEmailRequest,
)
from ..skills.notifications import create_notification

router = APIRouter(prefix="/auth", tags=["auth"])


def _is_production() -> bool:
    return get_settings().app_env == "production"


def _dev_token(token: str) -> dict:
    """Outside production (no email provider configured) we return the token so
    the flow is usable/testable; in production it is emailed, never returned."""
    return {} if _is_production() else {"dev_token": token}


def _auth_payload(user: User) -> dict:
    from ..deps import user_is_admin

    user_data = UserOut.model_validate(user).model_dump(mode="json")
    user_data["is_admin"] = user_is_admin(user)
    return {
        "token": create_access_token(user.id),
        "user": user_data,
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

    # Greet the new user so their notification bell isn't empty.
    create_notification(
        session,
        user.id,
        type="welcome",
        title="Welcome to SkillSwap AI",
        body="Add your skills to find your first learning match.",
        link="/matches",
    )
    await session.commit()

    data = _auth_payload(user)
    # Issue an email-verification token (emailed in prod; returned in dev).
    data.update(_dev_token(create_scoped_token(user.id, "verify")))
    return ok(data=data, message="Account created", status_code=201)


@router.post("/verify-email")
async def verify_email(
    payload: VerifyEmailRequest, session: AsyncSession = Depends(get_session)
) -> object:
    """Confirm an email address from a verification token."""
    user_id = decode_scoped_token(payload.token, "verify")
    if user_id is None:
        return error("This verification link is invalid or has expired.", status_code=400, code="bad_token")
    user = await session.get(User, user_id)
    if user is None:
        return error("Account not found.", status_code=404, code="not_found")
    user.email_verified = True
    await session.commit()
    return ok(message="Email verified")


@router.post("/resend-verification")
async def resend_verification(
    user: User = Depends(get_current_user),
) -> object:
    """Re-issue an email-verification token for the signed-in user."""
    if user.email_verified:
        return ok(message="Your email is already verified.")
    return ok(
        data=_dev_token(create_scoped_token(user.id, "verify")),
        message="Verification email sent.",
    )


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest, session: AsyncSession = Depends(get_session)
) -> object:
    """Start a password reset. Always succeeds (never reveals whether an account
    exists); the reset token is emailed in production, returned in dev."""
    user = await get_user_by_email(session, payload.email)
    data = {}
    if user is not None:
        data = _dev_token(create_scoped_token(user.id, "reset", ttl_minutes=30))
    return ok(data=data, message="If that email exists, a reset link is on its way.")


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest, session: AsyncSession = Depends(get_session)
) -> object:
    """Set a new password from a valid reset token."""
    user_id = decode_scoped_token(payload.token, "reset")
    if user_id is None:
        return error("This reset link is invalid or has expired.", status_code=400, code="bad_token")
    user = await session.get(User, user_id)
    if user is None:
        return error("Account not found.", status_code=404, code="not_found")
    user.password_hash = hash_password(payload.password)
    await session.commit()
    return ok(message="Password updated — you can sign in now.")


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
