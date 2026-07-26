"""skill assessments: AI-graded skill verification quizzes

Revision ID: 0025_skill_assessments
Revises: 0024_referrals
Create Date: 2026-07-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_skill_assessments"
down_revision: Union[str, None] = "0024_referrals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skill_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("skill_name", sa.String(length=255), nullable=False),
        sa.Column("skill_normalized", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_skill_assessments_user_id", "skill_assessments", ["user_id"])
    op.create_index("ix_skill_assessments_skill_normalized", "skill_assessments", ["skill_normalized"])
    op.create_index("ix_skill_assessments_status", "skill_assessments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_skill_assessments_status", table_name="skill_assessments")
    op.drop_index("ix_skill_assessments_skill_normalized", table_name="skill_assessments")
    op.drop_index("ix_skill_assessments_user_id", table_name="skill_assessments")
    op.drop_table("skill_assessments")
