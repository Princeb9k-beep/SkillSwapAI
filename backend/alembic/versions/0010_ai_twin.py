"""ai twin: style profiles + twin conversations (spec §4)

Revision ID: 0010_ai_twin
Revises: 0009_challenges
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_ai_twin"
down_revision: Union[str, None] = "0009_challenges"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_twins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("style_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("trained", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_ai_twin_user"),
    )
    op.create_index("ix_ai_twins_user_id", "ai_twins", ["user_id"], unique=True)

    op.create_table(
        "twin_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("twin_owner_id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["twin_owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_twin_messages_twin_owner_id", "twin_messages", ["twin_owner_id"])
    op.create_index("ix_twin_messages_learner_id", "twin_messages", ["learner_id"])


def downgrade() -> None:
    op.drop_index("ix_twin_messages_learner_id", table_name="twin_messages")
    op.drop_index("ix_twin_messages_twin_owner_id", table_name="twin_messages")
    op.drop_table("twin_messages")

    op.drop_index("ix_ai_twins_user_id", table_name="ai_twins")
    op.drop_table("ai_twins")
