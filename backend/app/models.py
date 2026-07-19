"""
SQLAlchemy ORM models — the six required tables.

users, skills, projects, lessons, roadmaps, interviews. JSON columns hold the
structured AI output (roadmap steps, interview Q&A) so we can evolve the shape
without a migration. Foreign keys use ON DELETE CASCADE so removing a user cleans
up their data. Indexes back every foreign key and common lookup column.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # e.g. "I want to make $80k as a data engineer"
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_income: Mapped[int | None] = mapped_column(Integer, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # --- Gamification ---
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default="0", index=True)
    level: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    streak: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_active_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    achievements: Mapped[list["Achievement"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    skills: Mapped[list["Skill"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    roadmaps: Mapped[list["Roadmap"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    interviews: Mapped[list["Interview"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    # Lowercased, trimmed `name` for exact-match joins in the matching engine.
    name_normalized: Mapped[str] = mapped_column(String(255), index=True, default="")
    # "have" (skills the user can teach) | "want" (skills the user wants to learn)
    kind: Mapped[str] = mapped_column(String(10), default="have", index=True)
    # peer-verified (spec §2.5) — set true when a verification request passes
    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # beginner | intermediate | advanced
    level: Mapped[str] = mapped_column(String(40), default="beginner")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="skills")
    projects: Mapped[list["Project"]] = relationship(back_populates="skill")


class Roadmap(Base):
    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    goal: Mapped[str] = mapped_column(Text)
    # {"summary": str, "milestones": [{"title", "skills", "weeks", "steps"}...]}
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="roadmaps")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="roadmap")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[int | None] = mapped_column(
        ForeignKey("skills.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # easy | medium | hard
    difficulty: Mapped[str] = mapped_column(String(40), default="medium")
    # suggested | in_progress | completed
    status: Mapped[str] = mapped_column(String(40), default="suggested", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="projects")
    skill: Mapped[Skill | None] = relationship(back_populates="projects")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    roadmap_id: Mapped[int | None] = mapped_column(
        ForeignKey("roadmaps.id", ondelete="SET NULL"), nullable=True, index=True
    )
    day: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="lessons")
    roadmap: Mapped[Roadmap | None] = relationship(back_populates="lessons")


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(255))
    questions: Mapped[list] = mapped_column(JSON, default=list)
    answers: Mapped[list] = mapped_column(JSON, default=list)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="interviews")


class MarketplaceListing(Base):
    __tablename__ = "marketplace_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    # tutoring | coaching | course | template
    kind: Mapped[str] = mapped_column(String(20), index=True, default="tutoring")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MarketplaceOrder(Base):
    __tablename__ = "marketplace_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    buyer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    commission_cents: Mapped[int] = mapped_column(Integer, default=0)
    # requested | confirmed | completed | cancelled
    status: Mapped[str] = mapped_column(String(20), default="requested", index=True)
    # set true by the (future) payment webhook — no fake payments here
    paid: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReputationReview(Base):
    __tablename__ = "reputation_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # the user being rated
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    teaching_quality: Mapped[int] = mapped_column(Integer)  # 1-5
    reliability: Mapped[int] = mapped_column(Integer)       # 1-5
    response_time: Mapped[int] = mapped_column(Integer)     # 1-5
    completed: Mapped[bool] = mapped_column(Boolean, default=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class VerificationRequest(Base):
    __tablename__ = "verification_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    skill_name: Mapped[str] = mapped_column(String(255))
    skill_normalized: Mapped[str] = mapped_column(String(255), index=True, default="")
    evidence_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pending | verified | rejected
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    approvals: Mapped[int] = mapped_column(Integer, default=0)
    rejections: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class VerificationReview(Base):
    __tablename__ = "verification_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("verification_requests.id", ondelete="CASCADE"), index=True
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # approve | reject
    vote: Mapped[str] = mapped_column(String(10))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Community(Base):
    __tablename__ = "communities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    name_normalized: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    topic: Mapped[str] = mapped_column(String(60), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CommunityMember(Base):
    __tablename__ = "community_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    community_id: Mapped[int] = mapped_column(
        ForeignKey("communities.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CommunityPost(Base):
    __tablename__ = "community_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    community_id: Mapped[int] = mapped_column(
        ForeignKey("communities.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date, index=True)  # one per user per calendar day
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CoachMessage(Base):
    __tablename__ = "coach_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # stable machine code, unique per user (e.g. "first_lesson", "streak_7")
    code: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="achievements")
