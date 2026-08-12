"""Authentication endpoints: signup and login."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    create_scoped_token,
    decode_scoped_token,
    hash_password,
    verify_password,
)
from ..background import run_in_background
from ..config import get_settings
from ..database import get_session
from ..deps import get_current_user, get_user_by_email
from ..mailer import (
    email_configured,
    send_event_email,
    send_password_reset_email,
    send_verification_email,
)
from ..models import User
from ..plans import add_purchased_tokens
from ..ratelimit import rate_limit
from ..referrals import bonus_tokens, find_referrer
from ..responses import error, ok
from ..schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
    VerifyEmailRequest,
)
from ..sessions import (
    active_session_count,
    issue_session,
    revoke_all_for_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from ..skills.notifications import create_notification

router = APIRouter(prefix="/auth", tags=["auth"])


def _is_production() -> bool:
    return get_settings().app_env == "production"


def _dev_token(token: str) -> dict:
    """When no email provider is configured we return the token so the flow is
    usable/testable; once SMTP is set (or in production) it's emailed, never
    returned."""
    if email_configured() or _is_production():
        return {}
    return {"dev_token": token}


@router.post("/signup", dependencies=[Depends(rate_limit("signup", 10, 3600))])
async def signup(
    payload: SignupRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
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
    # Apply a referral code (if valid and not self) — credit bonus tokens to
    # both the new user and the inviter.
    referrer = None
    if payload.referral_code:
        referrer = await find_referrer(session, payload.referral_code)
        if referrer is not None:
            user.referred_by_id = referrer.id

    session.add(user)
    await session.commit()
    await session.refresh(user)  # need created_at for UserOut

    if referrer is not None:
        bonus = bonus_tokens()
        await add_purchased_tokens(session, user, bonus)
        await add_purchased_tokens(session, referrer, bonus)
        create_notification(
            session,
            referrer.id,
            type="referral",
            title="Someone joined with your invite! 🎉",
            body=f"You earned {bonus} bonus AI tokens.",
            link="/settings",
        )
        run_in_background(
            send_event_email(
                referrer,
                "referral",
                "Someone joined with your invite! 🎉",
                f"You earned {bonus} bonus AI tokens. Thanks for spreading the word!",
                "/settings",
            ),
            name="referral-email",
        )

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

    data = await issue_session(session, user, request.headers.get("user-agent"))
    # Issue an email-verification token — email it when SMTP is configured,
    # otherwise fall back to returning it so the dev flow still works.
    token = create_scoped_token(user.id, "verify")
    run_in_background(send_verification_email(user.email, user.name, token), name="verify-email")
    data.update(_dev_token(token))
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


@router.post(
    "/resend-verification",
    dependencies=[Depends(rate_limit("resend", 5, 3600))],
)
async def resend_verification(
    user: User = Depends(get_current_user),
) -> object:
    """Re-issue an email-verification token and report what actually happened.

    Unlike a fire-and-forget send, this awaits the mailer so the response tells
    the truth: whether email delivery is configured on the server and whether the
    message was actually sent — surfaced to the user instead of a silent no-op.
    """
    if user.email_verified:
        return ok(message="Your email is already verified.")
    token = create_scoped_token(user.id, "verify")
    configured = email_configured()
    sent = await send_verification_email(user.email, user.name, token)
    data = {"email_sent": sent, "email_configured": configured}

    if not configured:
        # Server has no SMTP provider set. Hand back the token off-production so
        # the client can still finish verifying; in production just say so.
        data.update(_dev_token(token))
        return ok(
            data=data,
            message="Email delivery isn't set up on the server yet, so no email was sent.",
        )
    if not sent:
        return error(
            "We couldn't send the verification email. Check the server's SMTP "
            "settings (host, port, username, and app password).",
            status_code=502,
            code="email_send_failed",
        )
    return ok(data=data, message="Verification email sent — check your inbox (and spam).")


@router.post("/forgot-password", dependencies=[Depends(rate_limit("forgot", 5, 3600))])
async def forgot_password(
    payload: ForgotPasswordRequest, session: AsyncSession = Depends(get_session)
) -> object:
    """Start a password reset. Always succeeds (never reveals whether an account
    exists); the reset token is emailed in production, returned in dev."""
    user = await get_user_by_email(session, payload.email)
    data = {}
    if user is not None:
        token = create_scoped_token(user.id, "reset", ttl_minutes=30)
        run_in_background(send_password_reset_email(user.email, user.name, token), name="reset-email")
        data = _dev_token(token)
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


@router.post("/login", dependencies=[Depends(rate_limit("login", 20, 900))])
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> object:
    """Authenticate and return an access + refresh token."""
    user = await get_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        return error(
            "Incorrect email or password.", status_code=401, code="bad_credentials"
        )
    data = await issue_session(session, user, request.headers.get("user-agent"))
    return ok(data=data, message="Signed in")


@router.post("/refresh", dependencies=[Depends(rate_limit("refresh", 60, 3600))])
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> object:
    """Exchange a refresh token for a new access + refresh token (rotation)."""
    data = await rotate_refresh_token(
        session, payload.refresh_token, request.headers.get("user-agent")
    )
    if data is None:
        return error("Session expired. Please sign in again.", status_code=401, code="bad_refresh")
    return ok(data=data, message="Refreshed")


@router.post("/logout")
async def logout(
    payload: LogoutRequest, session: AsyncSession = Depends(get_session)
) -> object:
    """Revoke a single refresh token (this device's session)."""
    if payload.refresh_token:
        await revoke_refresh_token(session, payload.refresh_token)
    return ok(message="Signed out")


@router.post("/logout-all")
async def logout_all(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Revoke every refresh token for the user (sign out everywhere)."""
    count = await revoke_all_for_user(session, user.id)
    return ok(data={"revoked": count}, message="Signed out of all devices.")


@router.get("/sessions")
async def sessions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """How many active (non-revoked, unexpired) sessions the user has."""
    return ok(data={"active": await active_session_count(session, user.id)})
