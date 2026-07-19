"""daily ai challenges (spec §3.8)

Revision ID: 0009_challenges
Revises: 0008_coach
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_challenges"
down_revision: Union[str, None] = "0008_coach"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_challenges_user_id", "challenges", ["user_id"])
    op.create_index("ix_challenges_day", "challenges", ["day"])


def downgrade() -> None:
    op.drop_index("ix_challenges_day", table_name="challenges")
    op.drop_index("ix_challenges_user_id", table_name="challenges")
    op.drop_table("challenges")
