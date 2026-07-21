"""AI support woven into every Academy lesson.

Given a lesson and a mode, produce tutor-style guidance via Groq — explain a
concept more deeply, hint at the hands-on exercise, or review a learner's
submitted work. Degrades gracefully to a helpful structured fallback when Groq
isn't configured, so the feature always works.
"""

from __future__ import annotations

from ..groq_client import AIUnavailableError, generate

_SYSTEM = (
    "You are an encouraging, expert tutor inside a hands-on skill course. "
    "Be concrete and practical. Keep answers focused and under ~200 words."
)


def _fallback(mode: str, lesson: dict, path: dict) -> str:
    t = lesson["title"]
    if mode == "review":
        return (
            f"Nice work practicing “{t}.” Check it against the lesson's steps: "
            f"{'; '.join(lesson['steps'])}. Ask yourself what you'd improve next, "
            "then move on and revisit if needed. (Set GROQ_API_KEY for personalized AI review.)"
        )
    if mode == "hint":
        return (
            f"For the exercise — {lesson['exercise']} — start small: do the simplest "
            f"version first, then expand. Re-read the worked example for “{t}” and copy "
            "its shape. (Set GROQ_API_KEY for tailored hints.)"
        )
    return (
        f"“{t}” (from {path['title']} → this module): {lesson['summary']} "
        f"Work the steps in order: {'; '.join(lesson['steps'])}. "
        "(Set GROQ_API_KEY to get a full AI explanation here.)"
    )


def _prompt(mode: str, lesson: dict, path: dict, question: str | None) -> str:
    ctx = (
        f"Course: {path['title']} ({path['difficulty']}). "
        f"Lesson: {lesson['title']}. Summary: {lesson['summary']} "
        f"Steps: {'; '.join(lesson['steps'])}. Exercise: {lesson['exercise']}."
    )
    if mode == "review":
        return (
            f"{ctx}\n\nThe learner submitted this work for the exercise:\n\n"
            f"{question or '(no submission text)'}\n\n"
            "Give specific, kind feedback: what's good, what to fix, and one next step."
        )
    if mode == "hint":
        return (
            f"{ctx}\n\nThe learner is stuck on the exercise"
            + (f' and asks: "{question}"' if question else "")
            + ".\n\nGive a helpful hint that guides without fully solving it."
        )
    return (
        f"{ctx}\n\n"
        + (f'The learner asks: "{question}"\n\n' if question else "")
        + "Explain this lesson clearly with a concrete example a beginner can follow."
    )


async def lesson_assist(
    path: dict, lesson: dict, mode: str, question: str | None
) -> dict:
    """Return AI guidance for a lesson. mode: explain | hint | review."""
    try:
        text = (await generate(
            _prompt(mode, lesson, path, question),
            system=_SYSTEM,
            max_tokens=500,
            temperature=0.4,
        )).strip()
        if text:
            return {"mode": mode, "answer": text}
    except AIUnavailableError:
        pass
    except Exception:
        pass
    return {"mode": mode, "answer": _fallback(mode, lesson, path), "fallback": True}
