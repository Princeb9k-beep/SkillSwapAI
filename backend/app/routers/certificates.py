"""Course-completion certificates: list your own, and a PUBLIC verify endpoint."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Certificate, User
from ..responses import error, ok

router = APIRouter(prefix="/certificates", tags=["certificates"])


async def issue_certificate(
    session: AsyncSession, user_id: int, slug: str, title: str
) -> Certificate | None:
    """Create a certificate for a completed course (idempotent). Caller commits."""
    existing = (
        await session.execute(
            select(Certificate).where(
                Certificate.user_id == user_id, Certificate.path_slug == slug
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    cert = Certificate(
        user_id=user_id, path_slug=slug, title=title, code=secrets.token_hex(6)
    )
    session.add(cert)
    return cert


def _dict(c: Certificate, holder: str | None = None) -> dict:
    d = {
        "id": c.id,
        "code": c.code,
        "title": c.title,
        "path_slug": c.path_slug,
        "issued_at": c.issued_at.isoformat() if c.issued_at else None,
    }
    if holder is not None:
        d["holder"] = holder
    return d


@router.get("")
async def my_certificates(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    rows = (
        await session.execute(
            select(Certificate)
            .where(Certificate.user_id == user.id)
            .order_by(Certificate.issued_at.desc())
        )
    ).scalars().all()
    return ok(data=[_dict(c) for c in rows])


@router.get("/verify/{code}")
async def verify(code: str, session: AsyncSession = Depends(get_session)) -> object:
    """PUBLIC: confirm a certificate is genuine (no auth — shareable link)."""
    cert = (
        await session.execute(select(Certificate).where(Certificate.code == code))
    ).scalar_one_or_none()
    if cert is None:
        return error("Certificate not found.", status_code=404, code="not_found")
    holder = await session.get(User, cert.user_id)
    return ok(data=_dict(cert, holder=holder.name if holder else "A SkillSwap learner"))
