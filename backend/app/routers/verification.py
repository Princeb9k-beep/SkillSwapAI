"""
Skill verification (spec §2.5) — peer-reviewed trust.

A user requests verification of a skill they can teach; peers vote approve/reject.
When approvals reach a threshold (and outweigh rejections) the request is verified:
the matching owned Skill is flagged `verified` and a badge is awarded. A second,
faster path is the AI assessment: a generated quiz the user passes to earn the
same verified flag without waiting on peers.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import (
    Achievement,
    Skill,
    SkillAssessment,
    User,
    VerificationRequest,
    VerificationReview,
)
from ..responses import error, ok
from ..schemas import AssessmentSubmit, ReviewCreate, VerificationCreate, VerificationQuizStart
from ..skills.verification_ai import generate_quiz

from ..plans import consume_ai_token, require_feature

router = APIRouter(prefix="/verifications", tags=["verification"])

# Net-vote thresholds to decide a request.
THRESHOLD = 2
# Fraction of AI-quiz questions the user must get right to pass.
ASSESSMENT_PASS = 0.8


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


@router.post("", dependencies=[Depends(require_feature("verification"))])
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
    await mark_skill_verified(session, req.user_id, req.skill_normalized)


async def mark_skill_verified(
    session: AsyncSession, user_id: int, skill_normalized: str
) -> None:
    """Flag the user's matching owned skill as verified + award the badge once."""
    skills = await session.execute(
        select(Skill).where(
            Skill.user_id == user_id,
            Skill.kind == "have",
            Skill.name_normalized == skill_normalized,
        )
    )
    for skill in skills.scalars().all():
        skill.verified = True

    have_badge = await session.execute(
        select(Achievement.id).where(
            Achievement.user_id == user_id, Achievement.code == "verified_skill"
        )
    )
    if have_badge.scalar_one_or_none() is None:
        session.add(
            Achievement(
                user_id=user_id,
                code="verified_skill",
                title="Verified",
                description="Had a skill verified.",
            )
        )


# --- AI assessment path ---------------------------------------------------

def _quiz_public(assessment: SkillAssessment) -> dict:
    """The client view of a quiz — questions + options only, no answer keys."""
    return {
        "id": assessment.id,
        "skill_name": assessment.skill_name,
        "status": assessment.status,
        "questions": [
            {"question": q["question"], "options": q["options"]}
            for q in assessment.questions
        ],
    }


@router.post(
    "/assessment",
    dependencies=[Depends(require_feature("verification")), Depends(consume_ai_token)],
)
async def start_assessment(
    payload: VerificationQuizStart,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Generate an AI quiz to verify a skill (an alternative to peer review)."""
    skill_name = payload.skill_name.strip()
    if len(skill_name) < 2:
        return error("Enter the skill you want to verify.", status_code=400, code="invalid")
    questions = await generate_quiz(skill_name)
    assessment = SkillAssessment(
        user_id=user.id,
        skill_name=skill_name,
        skill_normalized=skill_name.lower(),
        questions=questions,
        status="pending",
    )
    session.add(assessment)
    await session.commit()
    await session.refresh(assessment)
    return ok(data=_quiz_public(assessment), message="Quiz ready", status_code=201)


@router.post("/assessment/{assessment_id}/submit")
async def submit_assessment(
    assessment_id: int,
    payload: AssessmentSubmit,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Grade the quiz. A passing score verifies the skill immediately."""
    assessment = await session.get(SkillAssessment, assessment_id)
    if assessment is None or assessment.user_id != user.id:
        return error("Assessment not found.", status_code=404, code="not_found")
    if assessment.status != "pending":
        return error("This assessment is already complete.", status_code=409, code="done")

    questions = assessment.questions
    answers = payload.answers
    correct = sum(
        1
        for i, q in enumerate(questions)
        if i < len(answers) and answers[i] == q["answer"]
    )
    total = len(questions)
    passed = total > 0 and correct >= round(ASSESSMENT_PASS * total)

    assessment.score = correct
    assessment.status = "passed" if passed else "failed"
    assessment.submitted_at = datetime.now(timezone.utc)
    if passed:
        await mark_skill_verified(session, user.id, assessment.skill_normalized)
    await session.commit()

    return ok(
        data={
            "passed": passed,
            "score": correct,
            "total": total,
            "skill_name": assessment.skill_name,
        },
        message="Skill verified! 🎉" if passed else "Not quite — review and try again.",
    )
