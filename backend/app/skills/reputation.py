"""
Reputation scoring (spec §3.6) — a weighted, multi-dimensional score that replaces
a single star rating. Deterministic, DB-only.

Each review rates three 1-5 dimensions (teaching quality, reliability, response time)
plus a session-completed flag. The reputation score (0-100) is a weighted blend:

    score = 100 * ( 0.35*teaching + 0.25*reliability + 0.20*response + 0.20*completion )

where the 1-5 dimension averages are normalized to 0-1 as (avg-1)/4 and `completion`
is the fraction of reviews marking the session completed. New users (no reviews) have
score = None so the UI can show "No reviews yet" rather than a misleading 0.
"""

from __future__ import annotations

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ReputationReview

_W_TEACH = 0.35
_W_RELIABLE = 0.25
_W_RESPONSE = 0.20
_W_COMPLETION = 0.20


def _norm(avg_1_5: float) -> float:
    return max(0.0, min(1.0, (avg_1_5 - 1) / 4))


async def scores_for(
    session: AsyncSession, user_ids: list[int]
) -> dict[int, dict]:
    """Batch-compute reputation summaries for many users in one query."""
    if not user_ids:
        return {}
    rows = await session.execute(
        select(
            ReputationReview.subject_id,
            func.count().label("n"),
            func.avg(ReputationReview.teaching_quality),
            func.avg(ReputationReview.reliability),
            func.avg(ReputationReview.response_time),
            func.avg(cast(ReputationReview.completed, Integer)),
        )
        .where(ReputationReview.subject_id.in_(user_ids))
        .group_by(ReputationReview.subject_id)
    )
    out: dict[int, dict] = {}
    for subject_id, n, teach, reliable, response, completion in rows.all():
        score = round(
            100
            * (
                _W_TEACH * _norm(float(teach))
                + _W_RELIABLE * _norm(float(reliable))
                + _W_RESPONSE * _norm(float(response))
                + _W_COMPLETION * float(completion)
            )
        )
        out[subject_id] = {
            "score": score,
            "count": int(n),
            "teaching_quality": round(float(teach), 1),
            "reliability": round(float(reliable), 1),
            "response_time": round(float(response), 1),
            "completion_rate": round(float(completion), 2),
        }
    # users with no reviews
    for uid in user_ids:
        out.setdefault(uid, {"score": None, "count": 0})
    return out


async def score_for(session: AsyncSession, user_id: int) -> dict:
    return (await scores_for(session, [user_id]))[user_id]
