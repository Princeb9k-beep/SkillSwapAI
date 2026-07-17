"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Users ----------------------------------------------------------------
class UserUpsert(BaseModel):
    email: EmailStr
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
