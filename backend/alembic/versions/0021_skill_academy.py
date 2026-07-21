"""skill academy: enrollments + lesson progress (paid AI-guided courses)

Revision ID: 0021_skill_academy
Revises: 0020_moderation
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_skill_academy"
down_revision: Union[str, None] = "0020_moderation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skill_enrollments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("path_slug", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "path_slug", name="uq_skill_enrollment"),
    )
    op.create_index("ix_skill_enrollments_user_id", "skill_enrollments", ["user_id"])
    op.create_index("ix_skill_enrollments_path_slug", "skill_enrollments", ["path_slug"])

    op.create_table(
        "skill_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("path_slug", sa.String(length=80), nullable=False),
        sa.Column("lesson_key", sa.String(length=20), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "path_slug", "lesson_key", name="uq_skill_progress"),
    )
    op.create_index("ix_skill_progress_user_id", "skill_progress", ["user_id"])
    op.create_index("ix_skill_progress_path_slug", "skill_progress", ["path_slug"])


def downgrade() -> None:
    op.drop_index("ix_skill_progress_path_slug", table_name="skill_progress")
    op.drop_index("ix_skill_progress_user_id", table_name="skill_progress")
    op.drop_table("skill_progress")
    op.drop_index("ix_skill_enrollments_path_slug", table_name="skill_enrollments")
    op.drop_index("ix_skill_enrollments_user_id", table_name="skill_enrollments")
    op.drop_table("skill_enrollments")
