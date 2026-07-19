"""
Skill verification (spec §2.5) — peer-reviewed trust.

A user requests verification of a skill they can teach; peers vote approve/reject.
When approvals reach a threshold (and outweigh rejections) the request is verified:
the matching owned Skill is flagged `verified` and a badge is awarded. The AI-
assessment path from the spec is deferred; this is the deterministic peer-review core.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Achievement, Skill, User, VerificationRequest, VerificationReview
from ..responses import error, ok
from ..schemas import ReviewCreate, VerificationCreate

router = APIRouter(prefix="/verifications", tags=["verification"])

# Net-vote thresholds to decide a request.
THRESHOLD = 2


def _request_dict(r: VerificationRequest) -> dict:
    return {
        "id": r.id,
        "skill_name": r.skill_name,
        "evidence_url": r.evidence_url,
        "description": r.description,
        "status": r.status,
        "approvals": r.approvals,
        "rejections": r.rejections,
    }


@router.post("")
async def create_request(
    payload: VerificationCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Request peer verification for a skill you can teach."""
    normalized = payload.skill_name.strip().lower()
    # avoid duplicate pending requests for the same skill
    dupe = await session.execute(
        select(VerificationRequest).where(
            VerificationRequest.user_id == user.id,
            VerificationRequest.skill_normalized == normalized,
            VerificationRequest.status == "pending",
        )
    )
    if dupe.scalar_one_or_none() is not None:
        return error("You already have a pending request for that skill.", status_code=409, code="pending")

    req = VerificationRequest(
        user_id=user.id,
        skill_name=payload.skill_name.strip(),
        skill_normalized=normalized,
        evidence_url=payload.evidence_url,
        description=payload.description,
    )
    session.add(req)
    await session.commit()
    return ok(data=_request_dict(req), message="Verification requested", status_code=201)


@router.get("/mine")
async def my_requests(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """My verification requests and their status."""
    rows = await session.execute(
        select(VerificationRequest)
        .where(VerificationRequest.user_id == user.id)
        .order_by(VerificationRequest.created_at.desc())
    )
    return ok(data=[_request_dict(r) for r in rows.scalars().all()])


@router.get("/queue")
async def review_queue(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Pending requests from OTHER users that I haven't reviewed yet."""
    reviewed = {
        r[0]
        for r in (
            await session.execute(
                select(VerificationReview.request_id).where(
                    VerificationReview.reviewer_id == user.id
                )
            )
        ).all()
    }
    rows = await session.execute(
        select(VerificationRequest, User.name)
        .join(User, User.id == VerificationRequest.user_id)
        .where(
            VerificationRequest.status == "pending",
            VerificationRequest.user_id != user.id,
        )
        .order_by(VerificationRequest.created_at.asc())
    )
    queue = [
        {**_request_dict(r), "requester": name or f"Learner #{r.user_id}"}
        for r, name in rows.all()
        if r.id not in reviewed
    ]
    return ok(data=queue)


@router.post("/{request_id}/review")
async def review(
    request_id: int,
    payload: ReviewCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Vote approve/reject on someone else's verification request."""
    req = await session.get(VerificationRequest, request_id)
    if req is None:
        return error("Request not found.", status_code=404, code="not_found")
    if req.user_id == user.id:
        return error("You can't review your own request.", status_code=403, code="forbidden")
    if req.status != "pending":
        return error("This request is already decided.", status_code=409, code="decided")

    existing = await session.execute(
        select(VerificationReview).where(
            VerificationReview.request_id == request_id,
            VerificationReview.reviewer_id == user.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return error("You already reviewed this.", status_code=409, code="reviewed")

    session.add(
        VerificationReview(
            request_id=request_id,
            reviewer_id=user.id,
            vote=payload.vote,
            comment=payload.comment,
        )
    )
    if payload.vote == "approve":
        req.approvals += 1
    else:
        req.rejections += 1

    # Decide the request if a side crossed the threshold and leads.
    if req.approvals >= THRESHOLD and req.approvals > req.rejections:
        req.status = "verified"
        req.decided_at = datetime.now(timezone.utc)
        await _mark_verified(session, req)
    elif req.rejections >= THRESHOLD and req.rejections > req.approvals:
        req.status = "rejected"
        req.decided_at = datetime.now(timezone.utc)

    await session.commit()
    return ok(data=_request_dict(req), message="Review submitted")


async def _mark_verified(session: AsyncSession, req: VerificationRequest) -> None:
    """Flag the requester's matching owned skill + award a badge."""
    skills = await session.execute(
        select(Skill).where(
            Skill.user_id == req.user_id,
            Skill.kind == "have",
            Skill.name_normalized == req.skill_normalized,
        )
    )
    for skill in skills.scalars().all():
        skill.verified = True

    have_badge = await session.execute(
        select(Achievement.id).where(
            Achievement.user_id == req.user_id, Achievement.code == "verified_skill"
        )
    )
    if have_badge.scalar_one_or_none() is None:
        session.add(
            Achievement(
                user_id=req.user_id,
                code="verified_skill",
                title="Verified",
                description="Had a skill peer-verified.",
            )
        )
