"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Auth -----------------------------------------------------------------
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


# --- Skills ---------------------------------------------------------------
class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255, examples=["FastAPI"])
    kind: str = Field(default="have", pattern="^(have|want)$")
    category: str | None = None
    level: str = Field(default="beginner")


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    kind: str
    verified: bool
    category: str | None
    level: str


# --- Matching -------------------------------------------------------------
class MatchOut(BaseModel):
    user_id: int
    name: str
    goal: str | None
    compatibility: int          # 0-100
    mutual: bool                # two-way swap (each can teach the other)
    they_teach_you: list[str]   # skills they have that you want
    you_teach_them: list[str]   # skills you have that they want
    reason: str


# --- Marketplace ----------------------------------------------------------
class ListingCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    kind: str = Field(default="tutoring", pattern="^(tutoring|coaching|course|template)$")
    description: str | None = Field(default=None, max_length=4000)
    price_cents: int = Field(ge=0, le=10_000_00, examples=[5000])


class OrderStatusUpdate(BaseModel):
    status: str = Field(pattern="^(confirmed|completed|cancelled)$")


# --- Reputation -----------------------------------------------------------
class ReputationReviewCreate(BaseModel):
    teaching_quality: int = Field(ge=1, le=5)
    reliability: int = Field(ge=1, le=5)
    response_time: int = Field(ge=1, le=5)
    completed: bool = True
    comment: str | None = Field(default=None, max_length=1000)


# --- Skill verification ---------------------------------------------------
class VerificationCreate(BaseModel):
    skill_name: str = Field(min_length=1, max_length=255)
    evidence_url: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)


class ReviewCreate(BaseModel):
    vote: str = Field(pattern="^(approve|reject)$")
    comment: str | None = Field(default=None, max_length=1000)


# --- Communities ----------------------------------------------------------
class CommunityCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    topic: str = Field(min_length=1, max_length=60, examples=["Coding"])
    description: str | None = Field(default=None, max_length=2000)


class CommunityOut(BaseModel):
    id: int
    name: str
    topic: str
    description: str | None
    member_count: int
    post_count: int
    joined: bool


class PostCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class PostOut(BaseModel):
    id: int
    user_name: str
    body: str
    created_at: datetime
    can_delete: bool


# --- Gamification ---------------------------------------------------------
class AchievementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    title: str
    description: str | None
    earned_at: datetime


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    name: str
    xp: int
    level: int


# --- Users ----------------------------------------------------------------
class ProfileUpdate(BaseModel):
    name: str | None = None
    goal: str | None = Field(default=None, examples=["I want to make $80k"])
    target_income: int | None = Field(default=None, examples=[80000])


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str | None
    goal: str | None
    target_income: int | None
    created_at: datetime


# --- Roadmap --------------------------------------------------------------
class RoadmapCreate(BaseModel):
    goal: str = Field(examples=["I want to make $80k as a backend engineer"])
    current_skills: list[str] = Field(default_factory=list)


class RoadmapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    goal: str
    content: dict
    created_at: datetime


# --- Projects -------------------------------------------------------------
class ProjectSuggestRequest(BaseModel):
    skill: str = Field(examples=["FastAPI"])
    level: str = Field(default="beginner")
    count: int = Field(default=3, ge=1, le=6)


class ProjectStatusUpdate(BaseModel):
    status: str = Field(examples=["in_progress", "completed"])


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None
    difficulty: str
    status: str


# --- Resume ---------------------------------------------------------------
class ResumeRequest(BaseModel):
    name: str
    target_role: str
    skills: list[str] = Field(default_factory=list)
    experience: str | None = None


# --- Interview ------------------------------------------------------------
class InterviewStartRequest(BaseModel):
    role: str = Field(examples=["Backend Engineer"])
    count: int = Field(default=5, ge=1, le=10)


class InterviewAnswerRequest(BaseModel):
    interview_id: int
    answers: list[str]


# --- Lessons --------------------------------------------------------------
class LessonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    day: int
    title: str
    content: str | None
    completed: bool
