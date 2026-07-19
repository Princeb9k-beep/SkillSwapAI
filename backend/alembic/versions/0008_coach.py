"""ai coach conversation history (spec §2.4)

Revision ID: 0008_coach
Revises: 0007_marketplace
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_coach"
down_revision: Union[str, None] = "0007_marketplace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coach_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_coach_messages_user_id", "coach_messages", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_coach_messages_user_id", table_name="coach_messages")
    op.drop_table("coach_messages")
