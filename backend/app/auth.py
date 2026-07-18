"""
Authentication helpers: password hashing + JWT access tokens.

Passwords are hashed with werkzeug (pbkdf2) and never stored in plaintext.
Access tokens are stateless JWTs signed with APP_SECRET_KEY, so no server-side
session store is needed (keeps Redis optional). The token carries the user id
in `sub` and a 7-day expiry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

from .config import get_settings

_ALGORITHM = "HS256"
_TOKEN_TTL = timedelta(days=7)


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return check_password_hash(password_hash, password)


def create_access_token(user_id: int) -> str:
    """Issue a signed JWT for a user id."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + _TOKEN_TTL,
    }
    return jwt.encode(payload, get_settings().app_secret_key, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Return the user id from a valid token, or None if invalid/expired."""
    try:
        payload = jwt.decode(
            token, get_settings().app_secret_key, algorithms=[_ALGORITHM]
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
