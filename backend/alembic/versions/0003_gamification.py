"""gamification: user xp/level/streak + achievements

Revision ID: 0003_gamification
Revises: 0002_skill_kind
Create Date: 2026-07-18

Adds XP/level/streak/last_active columns to users and an achievements table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_gamification"
down_revision: Union[str, None] = "0002_skill_kind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("xp", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("level", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("users", sa.Column("streak", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("last_active_on", sa.Date(), nullable=True))
    op.create_index("ix_users_xp", "users", ["xp"])

    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("earned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_achievements_user_id", "achievements", ["user_id"])
    op.create_index("ix_achievements_code", "achievements", ["code"])


def downgrade() -> None:
    op.drop_index("ix_achievements_code", table_name="achievements")
    op.drop_index("ix_achievements_user_id", table_name="achievements")
    op.drop_table("achievements")

    op.drop_index("ix_users_xp", table_name="users")
    op.drop_column("users", "last_active_on")
    op.drop_column("users", "streak")
    op.drop_column("users", "level")
    op.drop_column("users", "xp")
