"""Reputation endpoints (spec §3.6): leave reviews + read weighted scores."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import ReputationReview, User
from ..responses import error, ok
from ..schemas import ReputationReviewCreate
from ..skills.reputation import score_for

router = APIRouter(prefix="/reputation", tags=["reputation"])


@router.get("/me")
async def my_reputation(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    return ok(data=await score_for(session, user.id))


@router.get("/{user_id}")
async def user_reputation(
    user_id: int,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Reputation summary + recent review comments for a user."""
    summary = await score_for(session, user_id)
    rows = await session.execute(
        select(ReputationReview, User.name)
        .join(User, User.id == ReputationReview.reviewer_id)
        .where(ReputationReview.subject_id == user_id)
        .order_by(ReputationReview.created_at.desc())
        .limit(10)
    )
    reviews = [
        {
            "reviewer": name or f"Learner #{r.reviewer_id}",
            "comment": r.comment,
            "completed": r.completed,
        }
        for r, name in rows.all()
        if r.comment
    ]
    return ok(data={**summary, "reviews": reviews})


@router.post("/{user_id}/review")
async def leave_review(
    user_id: int,
    payload: ReputationReviewCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Rate another user after a session."""
    if user_id == user.id:
        return error("You can't review yourself.", status_code=403, code="forbidden")
    subject = await session.get(User, user_id)
    if subject is None:
        return error("User not found.", status_code=404, code="not_found")

    session.add(
        ReputationReview(
            subject_id=user_id,
            reviewer_id=user.id,
            teaching_quality=payload.teaching_quality,
            reliability=payload.reliability,
            response_time=payload.response_time,
            completed=payload.completed,
            comment=payload.comment,
        )
    )
    await session.commit()
    return ok(data=await score_for(session, user_id), message="Review submitted", status_code=201)
