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


async def send_email(to: str, subject: str, text: str, html: str) -> bool:
    """Send an email. Returns True if sent, False if SMTP isn't configured or the
    send failed (the caller decides how to degrade). Never raises."""
    if not email_configured():
        logger.info("SMTP not configured — skipping email to %s (%r)", to, subject)
        return False
    try:
        await asyncio.to_thread(_send_sync, to, subject, text, html)
        logger.info("Sent email to %s (%r)", to, subject)
        return True
    except Exception as exc:  # noqa: BLE001 — degrade, don't crash the request
        logger.warning("Failed to send email to %s: %s", to, exc)
        return False


# --- Templates -----------------------------------------------------------

def _frontend_url(path: str) -> str:
    base = get_settings().frontend_url.rstrip("/")
    return f"{base}{path}"


def _shell(title: str, intro: str, button_label: str, url: str, footer: str) -> str:
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;background:#f7f8fb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1c25;">
    <div style="max-width:480px;margin:0 auto;padding:32px 24px;">
      <div style="font-size:20px;font-weight:800;margin-bottom:16px;">SkillSwap<span style="color:#4f46e5;">AI</span></div>
      <div style="background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:28px;">
        <h1 style="font-size:19px;margin:0 0 12px;">{title}</h1>
        <p style="font-size:15px;line-height:1.5;color:#374151;margin:0 0 22px;">{intro}</p>
        <a href="{url}" style="display:inline-block;background:#4f46e5;color:#fff;text-decoration:none;font-weight:600;padding:12px 20px;border-radius:10px;font-size:15px;">{button_label}</a>
        <p style="font-size:13px;color:#6b7280;margin:22px 0 0;line-height:1.5;">Or paste this link into your browser:<br><span style="color:#4f46e5;word-break:break-all;">{url}</span></p>
      </div>
      <p style="font-size:12px;color:#9aa1ad;margin:18px 0 0;">{footer}</p>
    </div>
  </body>
</html>"""


async def send_verification_email(to: str, name: str | None, token: str) -> bool:
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
    return await send_email(to, "Confirm your SkillSwap AI email", text, html)


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
