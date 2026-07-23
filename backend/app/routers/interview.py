"""Interview practice endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Interview, User
from ..responses import error, ok
from ..schemas import InterviewAnswerRequest, InterviewStartRequest
from ..skills.interview import evaluate_answers, generate_questions

from ..plans import require_feature

router = APIRouter(prefix="/interview", tags=["interview"])


@router.post("/start", dependencies=[Depends(require_feature("career_tools"))])
async def start(
    payload: InterviewStartRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Begin a mock interview: generate and store questions."""
    questions = await generate_questions(payload.role, payload.count)
    interview = Interview(user_id=user.id, role=payload.role, questions=questions)
    session.add(interview)
    await session.commit()
    # id is set on commit; response carries no server-generated columns.
    return ok(
        data={"interview_id": interview.id, "role": interview.role, "questions": questions},
        message="Interview started",
    )


@router.post("/answer", dependencies=[Depends(require_feature("career_tools"))])
async def answer(
    payload: InterviewAnswerRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Submit answers and receive an AI score + feedback."""
    interview = await session.get(Interview, payload.interview_id)
    if interview is None or interview.user_id != user.id:
        return error("Interview not found.", status_code=404, code="not_found")

    result = await evaluate_answers(interview.role, interview.questions, payload.answers)
    interview.answers = payload.answers
    interview.feedback = result["feedback"]
    interview.score = result["score"]
    await session.commit()
    return ok(
        data={"score": result["score"], "feedback": result["feedback"]},
        message="Answers evaluated",
    )
