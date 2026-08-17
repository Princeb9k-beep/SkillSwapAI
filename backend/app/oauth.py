"""OAuth sign-in (Google / GitHub / LinkedIn / Discord / Microsoft).

Config-gated: a provider is available only when its client id + secret are set,
so the whole feature degrades to "not offered" out of the box. The flow is the
standard authorization-code grant — build an authorize URL, then exchange the
returned code for the user's email and create/find the account.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from .config import get_settings

PROVIDERS = ("google", "github", "linkedin", "discord", "microsoft")


def _redirect_uri() -> str:
    s = get_settings()
    base = (s.oauth_redirect_base or s.frontend_url).rstrip("/")
    return f"{base}/oauth/callback"


def _creds(provider: str) -> tuple[str, str]:
    """(client_id, client_secret) for a provider, or ('', '') if unset."""
    s = get_settings()
    return {
        "google": (s.google_client_id, s.google_client_secret),
        "github": (s.github_client_id, s.github_client_secret),
        "linkedin": (s.linkedin_client_id, s.linkedin_client_secret),
        "discord": (s.discord_client_id, s.discord_client_secret),
        "microsoft": (s.microsoft_client_id, s.microsoft_client_secret),
    }.get(provider, ("", ""))


def provider_enabled(provider: str) -> bool:
    cid, secret = _creds(provider)
    return bool(cid and secret)


def available_providers() -> list[str]:
    return [p for p in PROVIDERS if provider_enabled(p)]


# Authorize endpoints + scopes per provider. Everything else about the URL is
# the same standard authorization-code request.
_AUTHORIZE = {
    "google": ("https://accounts.google.com/o/oauth2/v2/auth", "openid email profile"),
    "github": ("https://github.com/login/oauth/authorize", "read:user user:email"),
    "linkedin": ("https://www.linkedin.com/oauth/v2/authorization", "openid profile email"),
    "discord": ("https://discord.com/oauth2/authorize", "identify email"),
    "microsoft": ("https://login.microsoftonline.com/common/oauth2/v2.0/authorize", "openid email profile"),
}


def authorize_url(provider: str, state: str) -> str:
    cid, _ = _creds(provider)
    base, scope = _AUTHORIZE[provider]
    params = {
        "client_id": cid,
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": scope,
        "state": state,
    }
    if provider == "google":
        params.update(access_type="online", prompt="select_account")
    if provider == "microsoft":
        params["response_mode"] = "query"
    return f"{base}?{urlencode(params)}"


async def exchange_code(provider: str, code: str) -> dict:
    """Exchange an auth code for the user's {email, name}. Raises on failure."""
    cid, secret = _creds(provider)
    redirect_uri = _redirect_uri()
    async with httpx.AsyncClient(timeout=15) as http:
        if provider == "google":
            tok = await http.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": cid,
                    "client_secret": secret,
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
                    "client_id": cid,
                    "client_secret": secret,
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

        if provider == "linkedin":
            tok = await http.post(
                "https://www.linkedin.com/oauth/v2/accessToken",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": cid,
                    "client_secret": secret,
                    "redirect_uri": redirect_uri,
                },
            )
            tok.raise_for_status()
            access = tok.json()["access_token"]
            info = await http.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {access}"},
            )
            info.raise_for_status()
            data = info.json()
            return {"email": data.get("email"), "name": data.get("name")}

        if provider == "discord":
            tok = await http.post(
                "https://discord.com/api/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": cid,
                    "client_secret": secret,
                    "redirect_uri": redirect_uri,
                },
            )
            tok.raise_for_status()
            access = tok.json()["access_token"]
            info = await http.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {access}"},
            )
            info.raise_for_status()
            data = info.json()
            # Discord only returns email when verified; require it.
            email = data.get("email") if data.get("verified") else None
            return {"email": email, "name": data.get("global_name") or data.get("username")}

        if provider == "microsoft":
            tok = await http.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": cid,
                    "client_secret": secret,
                    "redirect_uri": redirect_uri,
                    "scope": "openid email profile",
                },
            )
            tok.raise_for_status()
            access = tok.json()["access_token"]
            info = await http.get(
                "https://graph.microsoft.com/oidc/userinfo",
                headers={"Authorization": f"Bearer {access}"},
            )
            info.raise_for_status()
            data = info.json()
            return {"email": data.get("email"), "name": data.get("name")}

    raise ValueError("unknown provider")
