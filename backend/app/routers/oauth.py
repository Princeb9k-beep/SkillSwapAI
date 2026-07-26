"""OAuth endpoints: list enabled providers, start the flow, handle the callback."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import create_access_token
from ..database import get_session
from ..deps import get_user_by_email, user_is_admin
from ..models import User
from ..oauth import authorize_url, available_providers, exchange_code, provider_enabled
from ..responses import error, ok
from ..schemas import OAuthCallback, UserOut
from ..skills.notifications import create_notification

router = APIRouter(prefix="/auth/oauth", tags=["auth"])


@router.get("/providers")
async def providers() -> object:
    """Which OAuth providers are configured (so the UI knows what to show)."""
    return ok(data={"providers": available_providers()})


@router.get("/{provider}/start")
async def start(provider: str) -> object:
    """Return the provider authorize URL for the SPA to redirect to."""
    if not provider_enabled(provider):
        return error("That sign-in method isn't available.", status_code=404, code="not_found")
    state = secrets.token_urlsafe(16)
    return ok(data={"url": authorize_url(provider, state), "state": state})


@router.post("/{provider}/callback")
async def callback(
    provider: str,
    payload: OAuthCallback,
    session: AsyncSession = Depends(get_session),
) -> object:
    """Exchange the code, then find or create the account and issue our JWT."""
    if not provider_enabled(provider):
        return error("That sign-in method isn't available.", status_code=404, code="not_found")
    try:
        profile = await exchange_code(provider, payload.code)
    except Exception:  # noqa: BLE001 — any provider/network error
        return error("Couldn't complete sign-in. Please try again.", status_code=400, code="oauth_failed")

    email = (profile.get("email") or "").strip().lower()
    if not email:
        return error(
            "Your provider didn't share a verified email, so we can't sign you in.",
            status_code=400,
            code="no_email",
        )

    user = await get_user_by_email(session, email)
    created = False
    if user is None:
        user = User(email=email, name=profile.get("name"), email_verified=True)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        created = True
        create_notification(
            session,
            user.id,
            type="welcome",
            title="Welcome to SkillSwap AI",
            body="Add your skills to find your first learning match.",
            link="/matches",
        )
        await session.commit()
    elif not user.email_verified:
        # A verified OAuth login confirms the address.
        user.email_verified = True
        await session.commit()

    user_data = UserOut.model_validate(user).model_dump(mode="json")
    user_data["is_admin"] = user_is_admin(user)
    return ok(
        data={"token": create_access_token(user.id), "user": user_data, "created": created},
        message="Signed in",
    )
