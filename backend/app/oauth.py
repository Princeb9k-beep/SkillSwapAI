"""OAuth sign-in (Google / GitHub).

Config-gated: a provider is available only when its client id + secret are set,
so the whole feature degrades to "not offered" out of the box. The flow is the
standard authorization-code grant — build an authorize URL, then exchange the
returned code for the user's email and create/find the account.
"""

from __future__ import annotations

import httpx

from .config import get_settings

PROVIDERS = ("google", "github")


def _redirect_uri() -> str:
    s = get_settings()
    base = (s.oauth_redirect_base or s.frontend_url).rstrip("/")
    return f"{base}/oauth/callback"


def provider_enabled(provider: str) -> bool:
    s = get_settings()
    if provider == "google":
        return bool(s.google_client_id and s.google_client_secret)
    if provider == "github":
        return bool(s.github_client_id and s.github_client_secret)
    return False


def available_providers() -> list[str]:
    return [p for p in PROVIDERS if provider_enabled(p)]


def authorize_url(provider: str, state: str) -> str:
    s = get_settings()
    redirect_uri = _redirect_uri()
    if provider == "google":
        from urllib.parse import urlencode

        params = {
            "client_id": s.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    if provider == "github":
        from urllib.parse import urlencode

        params = {
            "client_id": s.github_client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    raise ValueError("unknown provider")


async def exchange_code(provider: str, code: str) -> dict:
    """Exchange an auth code for the user's {email, name}. Raises on failure."""
    s = get_settings()
    redirect_uri = _redirect_uri()
    async with httpx.AsyncClient(timeout=15) as http:
        if provider == "google":
            tok = await http.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": s.google_client_id,
                    "client_secret": s.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            tok.raise_for_status()
            access = tok.json()["access_token"]
            info = await http.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access}"},
            )
            info.raise_for_status()
            data = info.json()
            return {"email": data.get("email"), "name": data.get("name")}

        if provider == "github":
            tok = await http.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "code": code,
                    "client_id": s.github_client_id,
                    "client_secret": s.github_client_secret,
                    "redirect_uri": redirect_uri,
                },
            )
            tok.raise_for_status()
            access = tok.json()["access_token"]
            headers = {"Authorization": f"Bearer {access}", "Accept": "application/vnd.github+json"}
            profile = await http.get("https://api.github.com/user", headers=headers)
            profile.raise_for_status()
            pdata = profile.json()
            email = pdata.get("email")
            if not email:  # fetch the primary verified email
                emails = await http.get("https://api.github.com/user/emails", headers=headers)
                emails.raise_for_status()
                primary = next(
                    (e for e in emails.json() if e.get("primary") and e.get("verified")),
                    None,
                )
                email = primary["email"] if primary else None
            return {"email": email, "name": pdata.get("name") or pdata.get("login")}

    raise ValueError("unknown provider")
