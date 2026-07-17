"""initial schema: users, skills, roadmaps, projects, lessons, interviews

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-17

Creates all six tables with foreign keys (ON DELETE CASCADE / SET NULL) and indexes
on every foreign key plus common lookup columns. `downgrade()` drops them in reverse
dependency order.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("target_income", sa.Integer(), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("level", sa.String(length=40), nullable=False, server_default="beginner"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_skills_user_id", "skills", ["user_id"])

    op.create_table(
        "roadmaps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_roadmaps_user_id", "roadmaps", ["user_id"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("difficulty", sa.String(length=40), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="suggested"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_projects_skill_id", "projects", ["skill_id"])
    op.create_index("ix_projects_status", "projects", ["status"])

    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("roadmap_id", sa.Integer(), nullable=True),
        sa.Column("day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["roadmap_id"], ["roadmaps.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_lessons_user_id", "lessons", ["user_id"])
    op.create_index("ix_lessons_roadmap_id", "lessons", ["roadmap_id"])

    op.create_table(
        "interviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=255), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=True),
        sa.Column("answers", sa.JSON(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_interviews_user_id", "interviews", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_interviews_user_id", table_name="interviews")
    op.drop_table("interviews")

    op.drop_index("ix_lessons_roadmap_id", table_name="lessons")
    op.drop_index("ix_lessons_user_id", table_name="lessons")
    op.drop_table("lessons")

    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_skill_id", table_name="projects")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_roadmaps_user_id", table_name="roadmaps")
    op.drop_table("roadmaps")

    op.drop_index("ix_skills_user_id", table_name="skills")
    op.drop_table("skills")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
