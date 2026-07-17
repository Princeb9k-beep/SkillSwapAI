"""Interview practice skill."""

from __future__ import annotations

from ..groq_client import generate_json


async def generate_questions(role: str, count: int) -> list[str]:
    """Generate interview questions for a role."""
    prompt = (
        f"Generate {count} realistic interview questions for a {role} role. "
        "Return a JSON array of strings only."
    )
    try:
        data = await generate_json(prompt, max_tokens=700)
        if isinstance(data, list):
            return [str(q) for q in data][:count]
        if isinstance(data, dict) and "questions" in data:
            return [str(q) for q in data["questions"]][:count]
    except Exception:  # noqa: BLE001
        pass
    return [f"Tell me about your experience relevant to a {role} role." for _ in range(count)]


async def evaluate_answers(
    role: str, questions: list[str], answers: list[str]
) -> dict:
    """Score and give feedback on a candidate's answers. Returns {score, feedback}."""
    qa = "\n".join(
        f"Q{i + 1}: {q}\nA{i + 1}: {a}"
        for i, (q, a) in enumerate(zip(questions, answers))
    )
    prompt = (
        f"You are interviewing a candidate for a {role} role. Evaluate these answers "
        f"and return JSON {{\"score\": number 0-100, \"feedback\": string}} with "
        f"specific, actionable feedback.\n\n{qa}"
    )
    try:
        data = await generate_json(prompt, max_tokens=800, temperature=0.4)
        if isinstance(data, dict):
            return {
                "score": int(data.get("score", 0)),
                "feedback": str(data.get("feedback", "")),
            }
    except Exception:  # noqa: BLE001
        pass
    return {
        "score": 0,
        "feedback": "Automated evaluation unavailable (configure GROQ_API_KEY).",
    }
