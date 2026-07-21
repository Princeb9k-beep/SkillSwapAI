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


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=2000)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=2000)
    password: str = Field(min_length=8, max_length=128)


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


class MatchFeedback(BaseModel):
    signal: str = Field(pattern="^(interested|dismissed)$")


# --- Skill Academy --------------------------------------------------------
class LessonAssistRequest(BaseModel):
    mode: str = Field(default="explain", pattern="^(explain|hint|review)$")
    question: str | None = Field(default=None, max_length=6000)


# --- Safety / moderation --------------------------------------------------
class ReportCreate(BaseModel):
    target_type: str = Field(pattern="^(user|message|post)$")
    target_id: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


# --- Local Meetups --------------------------------------------------------
class MeetupCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    location: str = Field(default="Online", min_length=1, max_length=200)
    starts_at: datetime
    capacity: int = Field(default=0, ge=0, le=100000)


# --- Company Partnerships -------------------------------------------------
class CompanyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    website: str | None = Field(default=None, max_length=300)


class ChallengeCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=6000)
    kind: str = Field(default="challenge", pattern="^(challenge|scholarship|internship)$")
    reward: str | None = Field(default=None, max_length=200)
    deadline: str | None = Field(default=None, max_length=60)


class SubmissionCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class SubmissionReview(BaseModel):
    status: str = Field(pattern="^(accepted|rejected)$")


# --- AI Coach -------------------------------------------------------------
class CoachChat(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


# --- AI Skill Scanner -----------------------------------------------------
class ScanRequest(BaseModel):
    text: str = Field(min_length=20, max_length=20000)


# --- Live translation -----------------------------------------------------
class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    target_language: str = Field(min_length=2, max_length=40)


# --- Video Practice Rooms -------------------------------------------------
class RoomCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120, examples=["Mock interview practice"])
    topic: str = Field(default="General", min_length=1, max_length=60)


class RoomNotesUpdate(BaseModel):
    notes: str = Field(default="", max_length=20000)


# --- Direct messaging -----------------------------------------------------
class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


# --- Web Push -------------------------------------------------------------
class PushSubscribe(BaseModel):
    endpoint: str = Field(min_length=1, max_length=500)
    keys: dict[str, str] = Field(default_factory=dict)


class PushUnsubscribe(BaseModel):
    endpoint: str = Field(min_length=1, max_length=500)


# --- AI Twin --------------------------------------------------------------
class TwinTrain(BaseModel):
    samples: str = Field(min_length=20, max_length=8000)


class TwinChat(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class TwinQuiz(BaseModel):
    topic: str = Field(min_length=1, max_length=200)


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
    notify_messages: bool | None = None
    notify_achievements: bool | None = None
    notify_product: bool | None = None
    onboarded: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str | None
    goal: str | None
    target_income: int | None
    notify_messages: bool
    notify_achievements: bool
    notify_product: bool
    onboarded: bool
    email_verified: bool
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
