"""Company Partnerships (spec §3.10): companies post challenges, scholarships,
and internships; learners submit; the company owner reviews submissions.

Prefixed under /partnerships to avoid colliding with the daily AI-challenges
router (/challenges) and the SPA's /challenges page route.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import (
    ChallengeSubmission,
    Company,
    CompanyChallenge,
    User,
)
from ..responses import error, ok
from ..schemas import ChallengeCreate, CompanyCreate, SubmissionCreate, SubmissionReview

router = APIRouter(prefix="/partnerships", tags=["partnerships"])


# --- Companies ------------------------------------------------------------
@router.get("/companies")
async def list_companies(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    rows = (await session.execute(select(Company).order_by(Company.id.desc()))).scalars().all()
    counts = dict(
        (await session.execute(
            select(CompanyChallenge.company_id, func.count()).group_by(
                CompanyChallenge.company_id
            )
        )).all()
    )
    data = [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "website": c.website,
            "challenge_count": counts.get(c.id, 0),
            "is_owner": c.created_by == user.id,
        }
        for c in rows
    ]
    return ok(data=data)


@router.post("/companies")
async def create_company(
    payload: CompanyCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    company = Company(
        name=payload.name.strip(),
        description=payload.description,
        website=payload.website,
        created_by=user.id,
    )
    session.add(company)
    await session.commit()
    return ok(
        data={"id": company.id, "name": company.name, "is_owner": True},
        message="Company created",
        status_code=201,
    )


@router.post("/companies/{company_id}/challenges")
async def create_challenge(
    company_id: int,
    payload: ChallengeCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Post a challenge/scholarship/internship (company owner only)."""
    company = await session.get(Company, company_id)
    if company is None:
        return error("Company not found.", status_code=404, code="not_found")
    if company.created_by != user.id:
        return error("Only the company owner can post.", status_code=403, code="forbidden")
    challenge = CompanyChallenge(
        company_id=company_id,
        title=payload.title.strip(),
        description=payload.description,
        kind=payload.kind,
        reward=payload.reward,
        deadline=payload.deadline,
    )
    session.add(challenge)
    await session.commit()
    return ok(data={"id": challenge.id}, message="Posted", status_code=201)


# --- Challenges (across companies) ---------------------------------------
@router.get("/challenges")
async def list_challenges(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """All open opportunities with the company name and my submission status."""
    rows = await session.execute(
        select(CompanyChallenge, Company.name, Company.created_by)
        .join(Company, Company.id == CompanyChallenge.company_id)
        .order_by(CompanyChallenge.id.desc())
        .limit(100)
    )
    challenges = rows.all()
    my_subs = dict(
        (await session.execute(
            select(ChallengeSubmission.challenge_id, ChallengeSubmission.status).where(
                ChallengeSubmission.user_id == user.id
            )
        )).all()
    )
    sub_counts = dict(
        (await session.execute(
            select(ChallengeSubmission.challenge_id, func.count()).group_by(
                ChallengeSubmission.challenge_id
            )
        )).all()
    )
    data = [
        {
            "id": ch.id,
            "company_id": ch.company_id,
            "company_name": cname,
            "title": ch.title,
            "description": ch.description,
            "kind": ch.kind,
            "reward": ch.reward,
            "deadline": ch.deadline,
            "my_status": my_subs.get(ch.id),
            "submission_count": sub_counts.get(ch.id, 0),
            "is_owner": owner == user.id,
        }
        for ch, cname, owner in challenges
    ]
    return ok(data=data)


@router.post("/challenges/{challenge_id}/submit")
async def submit(
    challenge_id: int,
    payload: SubmissionCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Submit to a challenge (one submission per user; re-submitting updates it)."""
    challenge = await session.get(CompanyChallenge, challenge_id)
    if challenge is None:
        return error("Opportunity not found.", status_code=404, code="not_found")
    existing = (
        await session.execute(
            select(ChallengeSubmission).where(
                ChallengeSubmission.challenge_id == challenge_id,
                ChallengeSubmission.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.content = payload.content.strip()
        existing.status = "submitted"
    else:
        session.add(
            ChallengeSubmission(
                challenge_id=challenge_id, user_id=user.id, content=payload.content.strip()
            )
        )
    await session.commit()
    return ok(message="Submitted", status_code=201)


@router.get("/challenges/{challenge_id}/submissions")
async def list_submissions(
    challenge_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """View submissions for a challenge (company owner only)."""
    challenge = await session.get(CompanyChallenge, challenge_id)
    if challenge is None:
        return error("Opportunity not found.", status_code=404, code="not_found")
    company = await session.get(Company, challenge.company_id)
    if company is None or company.created_by != user.id:
        return error("Only the company owner can view submissions.", status_code=403, code="forbidden")
    rows = await session.execute(
        select(ChallengeSubmission, User.name)
        .join(User, User.id == ChallengeSubmission.user_id)
        .where(ChallengeSubmission.challenge_id == challenge_id)
        .order_by(ChallengeSubmission.created_at.desc())
    )
    data = [
        {
            "id": s.id,
            "user_name": name or f"Learner #{s.user_id}",
            "content": s.content,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s, name in rows.all()
    ]
    return ok(data=data)


@router.post("/submissions/{submission_id}/review")
async def review_submission(
    submission_id: int,
    payload: SubmissionReview,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Accept or reject a submission (company owner only)."""
    submission = await session.get(ChallengeSubmission, submission_id)
    if submission is None:
        return error("Submission not found.", status_code=404, code="not_found")
    challenge = await session.get(CompanyChallenge, submission.challenge_id)
    company = await session.get(Company, challenge.company_id) if challenge else None
    if company is None or company.created_by != user.id:
        return error("Only the company owner can review.", status_code=403, code="forbidden")
    submission.status = payload.status
    await session.commit()
    return ok(message=f"Submission {payload.status}")
