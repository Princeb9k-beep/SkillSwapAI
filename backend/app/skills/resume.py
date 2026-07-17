"""Resume builder skill."""

from __future__ import annotations

from ..groq_client import generate


async def build_resume(
    name: str, target_role: str, skills: list[str], experience: str | None
) -> str:
    """Generate a clean, ATS-friendly markdown resume tailored to a target role."""
    skills_str = ", ".join(skills) if skills else "(none provided)"
    prompt = (
        f"Write a concise, ATS-friendly resume in Markdown for {name}, targeting the "
        f"role of {target_role}. Skills: {skills_str}. "
        f"Experience notes: {experience or 'entry-level / career-changer'}. "
        "Include sections: Summary, Skills, Experience, Projects, Education. "
        "Use strong action verbs and quantified impact where plausible."
    )
    try:
        return await generate(prompt, max_tokens=1200, temperature=0.5)
    except Exception:  # noqa: BLE001
        return (
            f"# {name}\n\n**Target role:** {target_role}\n\n"
            f"## Skills\n{skills_str}\n\n"
            "_AI resume generation is unavailable (configure GROQ_API_KEY)._"
        )
