"""Transactional email.

Sends verification and password-reset emails over SMTP when it's configured
(``SMTP_HOST`` set). SMTP is a threadpool-bound stdlib client, so sends run in a
worker thread to avoid blocking the event loop. When SMTP is *not* configured the
mailer is a no-op that returns ``False``, and callers fall back to returning a
dev token — the app keeps working with no email provider, matching how Redis and
Groq degrade gracefully.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from .config import get_settings

logger = logging.getLogger("skillswap.mailer")


def email_configured() -> bool:
    return get_settings().email_configured


def _send_sync(to: str, subject: str, text: str, html: str) -> None:
    """Blocking SMTP send — run via ``asyncio.to_thread``."""
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    if s.smtp_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=context, timeout=15) as smtp:
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            if s.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)


def _friendly_smtp_error(exc: Exception) -> str:
    """Turn a raw SMTP exception into a short, actionable hint for the user."""
    msg = str(exc).strip()
    low = msg.lower()
    if (
        "username and password not accepted" in low
        or "5.7.8" in low
        or "authentication failed" in low
        or "invalid login" in low
    ):
        return (
            "the email account rejected the login. For Gmail: turn on 2-Step "
            "Verification and use a 16-character App Password (not your normal "
            "password), and set SMTP_USER / EMAIL_FROM to that same Gmail address"
        )
    if "application-specific password required" in low or "5.7.9" in low:
        return "Gmail needs an App Password — enable 2-Step Verification, then generate one"
    if "must issue a starttls" in low or "starttls" in low:
        return "the server requires STARTTLS — set SMTP_STARTTLS=True and SMTP_PORT=587"
    if "getaddrinfo" in low or "name or service not known" in low or "connection refused" in low:
        return "couldn't reach the mail server — check SMTP_HOST and SMTP_PORT"
    if "timed out" in low or "timeout" in low:
        return "the mail server didn't respond — check SMTP_HOST / SMTP_PORT (try 587)"
    return msg[:200] or "unknown SMTP error"


async def send_email_result(to: str, subject: str, text: str, html: str) -> str | None:
    """Send an email; return None on success, or a short error string on failure.
    Never raises. Use this where the caller wants to surface the reason."""
    if not email_configured():
        logger.info("SMTP not configured — skipping email to %s (%r)", to, subject)
        return "email delivery isn't configured on the server"
    try:
        await asyncio.to_thread(_send_sync, to, subject, text, html)
        logger.info("Sent email to %s (%r)", to, subject)
        return None
    except Exception as exc:  # noqa: BLE001 — degrade, don't crash the request
        logger.warning("Failed to send email to %s: %s", to, exc)
        return _friendly_smtp_error(exc)


async def send_email(to: str, subject: str, text: str, html: str) -> bool:
    """Send an email. Returns True if sent, False otherwise (never raises)."""
    return (await send_email_result(to, subject, text, html)) is None


# --- Templates -----------------------------------------------------------

def _frontend_url(path: str) -> str:
    base = get_settings().frontend_url.rstrip("/")
    return f"{base}{path}"


def _shell(title: str, intro: str, button_label: str, url: str, footer: str) -> str:
    # Matches the app's "Graphite + Serif · Ink" theme. Email clients don't load
    # webfonts reliably, so the serif uses Georgia (near-universally available)
    # and the accent is the ink-blue used across the product. All styles inline.
    serif = "Georgia,'Times New Roman',serif"
    sans = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;background:#fafafa;font-family:{sans};color:#161618;">
    <div style="max-width:480px;margin:0 auto;padding:32px 24px;">
      <div style="font-family:{serif};font-size:21px;font-weight:700;letter-spacing:-0.01em;margin-bottom:16px;">SkillSwap<span style="color:#2e4a76;">AI</span></div>
      <div style="background:#ffffff;border:1px solid #e5e5e8;border-radius:10px;padding:28px;">
        <h1 style="font-family:{serif};font-size:20px;line-height:1.25;margin:0 0 12px;color:#161618;">{title}</h1>
        <p style="font-size:15px;line-height:1.55;color:#4b4d55;margin:0 0 22px;">{intro}</p>
        <a href="{url}" style="display:inline-block;background:#2e4a76;color:#ffffff;text-decoration:none;font-weight:600;padding:12px 20px;border-radius:10px;font-size:15px;">{button_label}</a>
        <p style="font-size:13px;color:#6f7178;margin:22px 0 0;line-height:1.55;">Or paste this link into your browser:<br><span style="color:#2e4a76;word-break:break-all;">{url}</span></p>
      </div>
      <p style="font-size:12px;color:#8a8f98;margin:18px 0 0;">{footer}</p>
    </div>
  </body>
</html>"""


async def send_verification_email(to: str, name: str | None, token: str) -> str | None:
    """Send the verification email; return None on success or an error string."""
    url = _frontend_url(f"/verify-email?token={token}")
    greeting = f"Hi {name}," if name else "Hi,"
    text = (
        f"{greeting}\n\nConfirm your email to finish setting up your SkillSwap AI "
        f"account:\n{url}\n\nIf you didn't sign up, you can ignore this email."
    )
    html = _shell(
        "Confirm your email",
        f"{greeting} confirm your email address to finish setting up your SkillSwap AI account.",
        "Verify email",
        url,
        "If you didn't create a SkillSwap AI account, you can safely ignore this email.",
    )
    return await send_email_result(to, "Confirm your SkillSwap AI email", text, html)


# Which notification preference gates each notification type's email.
_PREF_BY_TYPE = {
    "message": "notify_messages",
    "achievement": "notify_achievements",
    "referral": "notify_achievements",
    "welcome": "notify_achievements",
    "match": "notify_messages",
    "meetup": "notify_messages",
    "reminder": "daily_reminder",
}


async def send_event_email(user, type: str, title: str, body: str | None, link: str | None) -> bool:
    """Email a user about an in-app event, respecting their notification prefs.
    No-op (returns False) when the relevant pref is off or SMTP is unconfigured."""
    pref = _PREF_BY_TYPE.get(type, "notify_product")
    if not getattr(user, pref, True):
        return False
    url = _frontend_url(link or "/")
    html = _shell(
        title,
        body or "You have a new update on SkillSwap AI.",
        "Open SkillSwap AI",
        url,
        "You're getting this because of your notification settings — change them anytime in Settings.",
    )
    text = f"{title}\n\n{body or ''}\n\n{url}"
    return await send_email(user.email, title, text, html)


async def send_password_reset_email(to: str, name: str | None, token: str) -> bool:
    url = _frontend_url(f"/reset-password?token={token}")
    greeting = f"Hi {name}," if name else "Hi,"
    text = (
        f"{greeting}\n\nReset your SkillSwap AI password here:\n{url}\n\n"
        "This link expires in 30 minutes. If you didn't request a reset, ignore this email."
    )
    html = _shell(
        "Reset your password",
        f"{greeting} we got a request to reset your SkillSwap AI password. This link expires in 30 minutes.",
        "Reset password",
        url,
        "If you didn't request a password reset, you can safely ignore this email — your password won't change.",
    )
    return await send_email(to, "Reset your SkillSwap AI password", text, html)
