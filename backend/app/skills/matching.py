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
from ..models import MatchSignal, Skill, User

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


async def _load_my_signals(session: AsyncSession, user_id: int) -> dict[int, str]:
    """partner_id -> signal for feedback this user has given ('dismissed'/'interested')."""
    rows = await session.execute(
        select(MatchSignal.partner_id, MatchSignal.signal).where(
            MatchSignal.user_id == user_id
        )
    )
    return {pid: sig for pid, sig in rows.all()}


async def _load_inbound_interested(session: AsyncSession, user_id: int) -> set[int]:
    """Users who marked *this* user as 'interested' — enables mutual-interest boosts."""
    rows = await session.execute(
        select(MatchSignal.user_id).where(
            MatchSignal.partner_id == user_id, MatchSignal.signal == "interested"
        )
    )
    return {r[0] for r in rows.all()}


def _signals_fingerprint(my_signals: dict[int, str]) -> str:
    raw = ",".join(f"{pid}:{sig}" for pid, sig in sorted(my_signals.items()))
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


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

    # Data-moat signals: my feedback (hide dismissed, boost interested) and who
    # has expressed interest in me (mutual interest ranks highest).
    my_signals = await _load_my_signals(session, user.id)
    interested_in_me = await _load_inbound_interested(session, user.id)

    # Fold both my signals AND who's interested in me into the cache key, so
    # feedback (mine or a partner's) takes effect on the next fetch.
    inbound = ",".join(str(i) for i in sorted(interested_in_me))
    fp = (
        _fingerprint(my_have, my_want)
        + ":" + _signals_fingerprint(my_signals)
        + ":" + hashlib.sha256(inbound.encode()).hexdigest()[:8]
    )
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
        if my_signals.get(cid) == "dismissed":
            continue  # respect the user's "not for me"
        their_have, their_want = await _load_skills(session, cid)
        score, mutual, they_teach, you_teach = _score(
            my_want, my_have, their_have, their_want
        )
        if score <= 0:
            continue
        display_name = cand.name or f"Learner #{cand.id}"
        i_am_interested = my_signals.get(cid) == "interested"
        mutual_interest = i_am_interested and cid in interested_in_me
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
                "interested": i_am_interested,
                "mutual_interest": mutual_interest,
            }
        )

    # Attach each candidate's reputation summary (one batch query).
    from .reputation import scores_for  # local import avoids a cycle

    reputations = await scores_for(session, [m["user_id"] for m in matches])
    for m in matches:
        rep = reputations.get(m["user_id"], {"score": None, "count": 0})
        m["reputation_score"] = rep["score"]
        m["reputation_count"] = rep["count"]
        m["match_score"] = _blended_score(m)

    # Rank: mutual-interest pairs first (both said "interested"), then by the
    # blended score (skill fit + reputation + interest signals), then breadth.
    matches.sort(
        key=lambda m: (
            m["mutual_interest"],
            m["match_score"],
            len(m["they_teach_you"]) + len(m["you_teach_them"]),
        ),
        reverse=True,
    )

    await cache_set(cache_key, matches, ttl=_CACHE_TTL)
    return matches[:limit]


def _blended_score(m: dict) -> int:
    """Rank score = skill compatibility, nudged by partner reputation and
    interest signals. This is the compounding 'data moat': the more feedback and
    reviews accumulate, the better ranking gets."""
    score = float(m["compatibility"])
    rep = m.get("reputation_score")
    if rep is not None:
        # Reputation 0-100 -> up to +/-8 around the neutral midpoint (50).
        score += (rep - 50) / 50 * 8
    if m.get("mutual_interest"):
        score += 15  # both marked interested — strongest signal
    elif m.get("interested"):
        score += 5   # I saved them
    return round(max(0, score))


async def record_signal(
    session: AsyncSession, user_id: int, partner_id: int, signal: str
) -> None:
    """Upsert a match signal (latest wins). No commit — caller commits."""
    existing = (
        await session.execute(
            select(MatchSignal).where(
                MatchSignal.user_id == user_id, MatchSignal.partner_id == partner_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.signal = signal
    else:
        session.add(MatchSignal(user_id=user_id, partner_id=partner_id, signal=signal))
