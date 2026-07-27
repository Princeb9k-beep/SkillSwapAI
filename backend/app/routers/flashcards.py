"""Flashcards with spaced repetition.

Generate cards for a topic (or a completed lesson), then review the ones due
today. A light SM-2-style schedule grows the interval on good/easy grades and
resets it on "again".
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Flashcard, Lesson, User
from ..plans import consume_ai_token
from ..responses import error, ok
from ..schemas import FlashcardGenerate, FlashcardReview
from ..skills.flashcards_ai import generate_cards

router = APIRouter(prefix="/flashcards", tags=["flashcards"])


def _card_dict(c: Flashcard) -> dict:
    return {
        "id": c.id,
        "topic": c.topic,
        "front": c.front,
        "back": c.back,
        "due_on": c.due_on.isoformat() if c.due_on else None,
        "reps": c.reps,
    }


@router.get("")
async def list_cards(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Counts + today's due cards."""
    today = date.today()
    total = (
        await session.execute(
            select(func.count()).select_from(Flashcard).where(Flashcard.user_id == user.id)
        )
    ).scalar_one()
    due = (
        await session.execute(
            select(Flashcard)
            .where(Flashcard.user_id == user.id, Flashcard.due_on <= today)
            .order_by(Flashcard.due_on.asc(), Flashcard.id.asc())
        )
    ).scalars().all()
    return ok(
        data={
            "total": int(total or 0),
            "due_count": len(due),
            "due": [_card_dict(c) for c in due],
        }
    )


@router.post("/generate", dependencies=[Depends(consume_ai_token)])
async def generate(
    payload: FlashcardGenerate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Generate a set of flashcards for a topic (optionally seeded by a lesson)."""
    topic = payload.topic.strip()
    source_text = None
    if payload.lesson_id is not None:
        lesson = await session.get(Lesson, payload.lesson_id)
        if lesson and lesson.user_id == user.id:
            topic = topic or lesson.title
            source_text = lesson.content
    if len(topic) < 2:
        return error("Enter a topic for your flashcards.", status_code=400, code="invalid")

    cards = await generate_cards(topic, source_text)
    today = date.today()
    created = []
    for c in cards:
        card = Flashcard(
            user_id=user.id, topic=topic, front=c["front"], back=c["back"], due_on=today
        )
        session.add(card)
        created.append(card)
    await session.commit()
    for card in created:
        await session.refresh(card)
    return ok(
        data={"cards": [_card_dict(c) for c in created]},
        message=f"Added {len(created)} flashcards for {topic}.",
        status_code=201,
    )


# Interval growth (days) per grade; "again" restarts the card.
def _next_interval(current: int, grade: str) -> int:
    if grade == "again":
        return 1
    if grade == "easy":
        return max(4, round((current or 1) * 3))
    # "good"
    if not current:
        return 2
    return max(2, round(current * 2.2))


@router.post("/{card_id}/review")
async def review(
    card_id: int,
    payload: FlashcardReview,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Grade a card (again/good/easy) and reschedule it."""
    card = await session.get(Flashcard, card_id)
    if card is None or card.user_id != user.id:
        return error("Card not found.", status_code=404, code="not_found")
    interval = _next_interval(card.interval_days, payload.grade)
    card.interval_days = interval
    card.reps = (card.reps or 0) + 1
    card.last_reviewed_on = date.today()
    card.due_on = date.today() + timedelta(days=interval)
    await session.commit()
    return ok(data={"id": card.id, "due_on": card.due_on.isoformat(), "interval_days": interval})


@router.delete("/{card_id}")
async def delete_card(
    card_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    card = await session.get(Flashcard, card_id)
    if card is None or card.user_id != user.id:
        return error("Card not found.", status_code=404, code="not_found")
    await session.delete(card)
    await session.commit()
    return ok(message="Card deleted")
