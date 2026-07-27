"""activity feed: activities + kudos

Revision ID: 0032_activity_feed
Revises: 0031_sessions
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032_activity_feed"
down_revision: Union[str, None] = "0031_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("text", sa.String(length=255), nullable=False),
        sa.Column("kudos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_activities_user_id", "activities", ["user_id"])
    op.create_index("ix_activities_kind", "activities", ["kind"])
    op.create_index("ix_activities_created_at", "activities", ["created_at"])

    op.create_table(
        "activity_kudos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("activity_id", "user_id", name="uq_activity_kudos"),
    )
    op.create_index("ix_activity_kudos_activity_id", "activity_kudos", ["activity_id"])
    op.create_index("ix_activity_kudos_user_id", "activity_kudos", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_activity_kudos_user_id", table_name="activity_kudos")
    op.drop_index("ix_activity_kudos_activity_id", table_name="activity_kudos")
    op.drop_table("activity_kudos")
    op.drop_index("ix_activities_created_at", table_name="activities")
    op.drop_index("ix_activities_kind", table_name="activities")
    op.drop_index("ix_activities_user_id", table_name="activities")
    op.drop_table("activities")
