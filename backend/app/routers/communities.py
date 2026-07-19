"""Communities: topic-based groups with membership and posts (spec §3.4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Community, CommunityMember, CommunityPost, User
from ..responses import error, ok
from ..schemas import CommunityCreate, PostCreate

router = APIRouter(prefix="/communities", tags=["communities"])


async def _is_member(session: AsyncSession, community_id: int, user_id: int) -> bool:
    row = await session.execute(
        select(CommunityMember.id).where(
            CommunityMember.community_id == community_id,
            CommunityMember.user_id == user_id,
        )
    )
    return row.scalar_one_or_none() is not None


async def _ensure_member(session: AsyncSession, community_id: int, user_id: int) -> None:
    if not await _is_member(session, community_id, user_id):
        session.add(CommunityMember(community_id=community_id, user_id=user_id))


@router.get("")
async def list_communities(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """List all communities with member/post counts and my membership flag."""
    communities = (await session.execute(select(Community).order_by(Community.id))).scalars().all()

    member_counts = dict(
        (await session.execute(
            select(CommunityMember.community_id, func.count())
            .group_by(CommunityMember.community_id)
        )).all()
    )
    post_counts = dict(
        (await session.execute(
            select(CommunityPost.community_id, func.count())
            .group_by(CommunityPost.community_id)
        )).all()
    )
    my = {
        r[0]
        for r in (await session.execute(
            select(CommunityMember.community_id).where(CommunityMember.user_id == user.id)
        )).all()
    }

    data = [
        {
            "id": c.id,
            "name": c.name,
            "topic": c.topic,
            "description": c.description,
            "member_count": member_counts.get(c.id, 0),
            "post_count": post_counts.get(c.id, 0),
            "joined": c.id in my,
        }
        for c in communities
    ]
    return ok(data=data)


@router.post("")
async def create_community(
    payload: CommunityCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Create a community; the creator auto-joins."""
    normalized = payload.name.strip().lower()
    existing = await session.execute(
        select(Community).where(Community.name_normalized == normalized)
    )
    if existing.scalar_one_or_none() is not None:
        return error("A community with that name already exists.", status_code=409, code="taken")

    community = Community(
        name=payload.name.strip(),
        name_normalized=normalized,
        topic=payload.topic.strip(),
        description=payload.description,
        created_by=user.id,
    )
    session.add(community)
    await session.flush()  # assign id
    session.add(CommunityMember(community_id=community.id, user_id=user.id))
    await session.commit()
    return ok(
        data={
            "id": community.id,
            "name": community.name,
            "topic": community.topic,
            "description": community.description,
            "member_count": 1,
            "post_count": 0,
            "joined": True,
        },
        message="Community created",
        status_code=201,
    )


@router.post("/{community_id}/join")
async def join(
    community_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    community = await session.get(Community, community_id)
    if community is None:
        return error("Community not found.", status_code=404, code="not_found")
    await _ensure_member(session, community_id, user.id)
    await session.commit()
    return ok(message="Joined")


@router.post("/{community_id}/leave")
async def leave(
    community_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    await session.execute(
        delete(CommunityMember).where(
            CommunityMember.community_id == community_id,
            CommunityMember.user_id == user.id,
        )
    )
    await session.commit()
    return ok(message="Left")


@router.get("/{community_id}")
async def community_detail(
    community_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Community detail with its posts (newest first)."""
    community = await session.get(Community, community_id)
    if community is None:
        return error("Community not found.", status_code=404, code="not_found")

    rows = await session.execute(
        select(CommunityPost, User.name)
        .join(User, User.id == CommunityPost.user_id)
        .where(CommunityPost.community_id == community_id)
        .order_by(CommunityPost.created_at.desc())
    )
    posts = [
        {
            "id": p.id,
            "user_name": name or f"Learner #{p.user_id}",
            "body": p.body,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "can_delete": p.user_id == user.id or community.created_by == user.id,
        }
        for p, name in rows.all()
    ]
    joined = await _is_member(session, community_id, user.id)
    return ok(
        data={
            "id": community.id,
            "name": community.name,
            "topic": community.topic,
            "description": community.description,
            "joined": joined,
            "posts": posts,
        }
    )


@router.post("/{community_id}/posts")
async def create_post(
    community_id: int,
    payload: PostCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Post to a community (auto-joins if not already a member)."""
    community = await session.get(Community, community_id)
    if community is None:
        return error("Community not found.", status_code=404, code="not_found")

    await _ensure_member(session, community_id, user.id)
    post = CommunityPost(community_id=community_id, user_id=user.id, body=payload.body.strip())
    session.add(post)
    await session.commit()
    return ok(
        data={
            "id": post.id,
            "user_name": user.name or f"Learner #{user.id}",
            "body": post.body,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "can_delete": True,
        },
        message="Posted",
        status_code=201,
    )


@router.delete("/{community_id}/posts/{post_id}")
async def delete_post(
    community_id: int,
    post_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Delete a post (author or community creator — light moderation)."""
    post = await session.get(CommunityPost, post_id)
    if post is None or post.community_id != community_id:
        return error("Post not found.", status_code=404, code="not_found")
    community = await session.get(Community, community_id)
    creator = community.created_by if community else None
    if post.user_id != user.id and creator != user.id:
        return error("You can't delete this post.", status_code=403, code="forbidden")
    await session.delete(post)
    await session.commit()
    return ok(message="Post removed")
