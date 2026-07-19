"""AI Twin endpoints (spec §4) — the differentiator."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import AITwin, Skill, TwinMessage, User
from ..responses import error, ok
from ..schemas import TwinChat, TwinQuiz, TwinTrain
from ..skills.twin import distill_style, twin_quiz, twin_reply

router = APIRouter(prefix="/twin", tags=["twin"])


async def _get_or_create(session: AsyncSession, user_id: int) -> AITwin:
    row = await session.execute(select(AITwin).where(AITwin.user_id == user_id))
    twin = row.scalar_one_or_none()
    if twin is None:
        twin = AITwin(user_id=user_id, style_prompt="", trained=False)
        session.add(twin)
        await session.flush()
    return twin


@router.get("/me")
async def my_twin(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    row = await session.execute(select(AITwin).where(AITwin.user_id == user.id))
    twin = row.scalar_one_or_none()
    return ok(
        data={
            "trained": bool(twin and twin.trained),
            "style_prompt": twin.style_prompt if twin else "",
        }
    )


@router.post("/train")
async def train(
    payload: TwinTrain,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Train (or retrain) my AI Twin from samples of how I teach."""
    twin = await _get_or_create(session, user.id)
    twin.style_prompt = await distill_style(payload.samples)
    twin.trained = True
    await session.commit()
    return ok(data={"trained": True, "style_prompt": twin.style_prompt}, message="Twin trained")


@router.get("/available")
async def available(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Other users whose twin is trained — pick one to learn from."""
    rows = await session.execute(
        select(AITwin, User.name)
        .join(User, User.id == AITwin.user_id)
        .where(AITwin.trained.is_(True), AITwin.user_id != user.id)
    )
    result = []
    for twin, name in rows.all():
        skills = await session.execute(
            select(Skill.name).where(Skill.user_id == twin.user_id, Skill.kind == "have")
        )
        result.append(
            {
                "owner_id": twin.user_id,
                "name": name or f"Learner #{twin.user_id}",
                "skills": [s[0] for s in skills.all()],
            }
        )
    return ok(data=result)


async def _load_owner_twin(session: AsyncSession, owner_id: int) -> tuple[User, AITwin] | None:
    owner = await session.get(User, owner_id)
    if owner is None:
        return None
    row = await session.execute(select(AITwin).where(AITwin.user_id == owner_id))
    twin = row.scalar_one_or_none()
    if twin is None or not twin.trained:
        return None
    return owner, twin


@router.get("/{owner_id}/history")
async def history(
    owner_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    rows = await session.execute(
        select(TwinMessage)
        .where(
            TwinMessage.twin_owner_id == owner_id,
            TwinMessage.learner_id == user.id,
        )
        .order_by(TwinMessage.id.asc())
    )
    return ok(data=[{"role": m.role, "content": m.content} for m in rows.scalars().all()])


@router.post("/{owner_id}/chat")
async def chat_with_twin(
    owner_id: int,
    payload: TwinChat,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Chat with another user's AI Twin."""
    found = await _load_owner_twin(session, owner_id)
    if found is None:
        return error("That twin isn't available.", status_code=404, code="not_found")
    owner, twin = found
    reply = await twin_reply(session, owner, twin.style_prompt, user, payload.message.strip())
    await session.commit()
    return ok(data={"reply": reply}, message="Twin replied")


@router.post("/{owner_id}/quiz")
async def quiz(
    owner_id: int,
    payload: TwinQuiz,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Get a quiz in a twin's teaching style on a topic."""
    found = await _load_owner_twin(session, owner_id)
    if found is None:
        return error("That twin isn't available.", status_code=404, code="not_found")
    owner, twin = found
    skills_rows = await session.execute(
        select(Skill.name).where(Skill.user_id == owner.id, Skill.kind == "have")
    )
    skills = ", ".join(s[0] for s in skills_rows.all()) or "general topics"
    questions = await twin_quiz(
        owner.name or f"Learner #{owner.id}", twin.style_prompt, skills, payload.topic
    )
    return ok(data={"questions": questions})
