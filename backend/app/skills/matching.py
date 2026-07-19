"""
AI Skill Matching — the primary SkillSwapAI feature (spec §2.1).

Complementary matching, "a dating app for learning": rank other users by how well
their owned skills cover what you want to learn, and how well your owned skills cover
what they want. Two-way (mutual) swaps rank highest.

The ranking is intentionally **deterministic** (per the spec's mandate): pure set
overlap + coverage weighting, no LLM in the hot path. Groq-based synonym expansion is
a documented future enhancement (normalize "JS"/"JavaScript") but is out of scope here
to keep results reproducible and cache-friendly.

Complexity: candidates are fetched with two indexed queries (owners of my wants,
wanters of my haves), so we never scan the full user table — only users with an actual
skill overlap are scored. Results are cached in Redis keyed by a fingerprint of the
requesting user's skills, so the cache self-invalidates when their skills change.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import cache_get, cache_set, make_key
from ..models import Skill, User

# Weight the value you gain slightly above what you give — you're the one searching.
_W_GAIN = 0.6
_W_GIVE = 0.4
_CACHE_TTL = 120  # seconds


def _norm(name: str) -> str:
    return name.strip().lower()


def _fingerprint(have: set[str], want: set[str]) -> str:
    raw = "h:" + ",".join(sorted(have)) + "|w:" + ",".join(sorted(want))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def _load_skills(session: AsyncSession, user_id: int) -> tuple[set[str], set[str]]:
    """Return (have, want) normalized skill-name sets for a user."""
    result = await session.execute(
        select(Skill.name_normalized, Skill.kind).where(Skill.user_id == user_id)
    )
    have: set[str] = set()
    want: set[str] = set()
    for name, kind in result.all():
        (want if kind == "want" else have).add(name)
    return have, want


def _score(my_want, my_have, their_have, their_want):
    """Compute (compatibility 0-100, mutual, they_teach, you_teach)."""
    they_teach = sorted(my_want & their_have)   # they satisfy my wants
    you_teach = sorted(their_want & my_have)    # I satisfy their wants
    coverage_me = len(they_teach) / max(1, len(my_want))
    coverage_them = len(you_teach) / max(1, len(their_want))
    score = round(100 * (_W_GAIN * coverage_me + _W_GIVE * coverage_them))
    mutual = bool(they_teach) and bool(you_teach)
    return score, mutual, they_teach, you_teach


def _reason(name, they_teach, you_teach, mutual) -> str:
    if mutual:
        return (
            f"Two-way swap: {name} can teach you {', '.join(they_teach)}, "
            f"and you can teach them {', '.join(you_teach)}."
        )
    if they_teach:
        return f"{name} can teach you {', '.join(they_teach)}."
    return f"You can teach {name} {', '.join(you_teach)}."


async def find_matches(
    session: AsyncSession, user: User, limit: int = 20
) -> list[dict]:
    """Return ranked complementary matches for `user`."""
    my_have, my_want = await _load_skills(session, user.id)
    if not my_have and not my_want:
        return []

    fp = _fingerprint(my_have, my_want)
    cache_key = make_key("matches", user.id, fp)
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached[:limit]

    # Candidate set: users who OWN something I want, or WANT something I own.
    # Two indexed queries on name_normalized + kind — no full-table scan.
    candidate_ids: set[int] = set()
    if my_want:
        rows = await session.execute(
            select(Skill.user_id)
            .where(Skill.kind == "have", Skill.name_normalized.in_(my_want))
            .where(Skill.user_id != user.id)
            .distinct()
        )
        candidate_ids.update(r[0] for r in rows.all())
    if my_have:
        rows = await session.execute(
            select(Skill.user_id)
            .where(Skill.kind == "want", Skill.name_normalized.in_(my_have))
            .where(Skill.user_id != user.id)
            .distinct()
        )
        candidate_ids.update(r[0] for r in rows.all())

    if not candidate_ids:
        await cache_set(cache_key, [], ttl=_CACHE_TTL)
        return []

    # Load candidate users + their skills.
    users_res = await session.execute(select(User).where(User.id.in_(candidate_ids)))
    users = {u.id: u for u in users_res.scalars().all()}

    matches: list[dict] = []
    for cid in candidate_ids:
        cand = users.get(cid)
        if cand is None:
            continue
        their_have, their_want = await _load_skills(session, cid)
        score, mutual, they_teach, you_teach = _score(
            my_want, my_have, their_have, their_want
        )
        if score <= 0:
            continue
        display_name = cand.name or f"Learner #{cand.id}"
        matches.append(
            {
                "user_id": cand.id,
                "name": display_name,
                "goal": cand.goal,
                "compatibility": score,
                "mutual": mutual,
                "they_teach_you": they_teach,
                "you_teach_them": you_teach,
                "reason": _reason(display_name, they_teach, you_teach, mutual),
            }
        )

    # Rank: mutual swaps first, then by compatibility, then by breadth of overlap.
    matches.sort(
        key=lambda m: (
            m["mutual"],
            m["compatibility"],
            len(m["they_teach_you"]) + len(m["you_teach_them"]),
        ),
        reverse=True,
    )

    await cache_set(cache_key, matches, ttl=_CACHE_TTL)
    return matches[:limit]
