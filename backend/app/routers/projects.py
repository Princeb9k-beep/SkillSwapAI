"""Project endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..deps import get_current_user
from ..models import Project, User
from ..responses import error, ok
from ..schemas import ProjectOut, ProjectStatusUpdate, ProjectSuggestRequest
from ..skills.projects import suggest_projects

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/suggest")
async def suggest(
    payload: ProjectSuggestRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    """Suggest and persist practice projects for a skill."""
    suggestions = await suggest_projects(payload.skill, payload.level, payload.count)
    created: list[Project] = []
    for s in suggestions:
        project = Project(
            user_id=user.id,
            title=s.get("title", "Untitled project"),
            description=s.get("description"),
            difficulty=s.get("difficulty", "medium"),
            status="suggested",
        )
        session.add(project)
        created.append(project)
    await session.commit()
    # ProjectOut needs no server-generated columns; ids are set on commit.
    return ok(
        data=[ProjectOut.model_validate(p).model_dump() for p in created],
        message=f"Suggested {len(created)} projects",
    )


@router.get("")
async def list_projects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    result = await session.execute(
        select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return ok(data=[ProjectOut.model_validate(p).model_dump() for p in projects])


@router.patch("/{project_id}")
async def update_status(
    project_id: int,
    payload: ProjectStatusUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> object:
    project = await session.get(Project, project_id)
    if project is None or project.user_id != user.id:
        return error("Project not found.", status_code=404, code="not_found")
    project.status = payload.status
    await session.commit()
    return ok(data=ProjectOut.model_validate(project).model_dump(), message="Status updated")
