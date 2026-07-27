"""scheduling: 1:1 session bookings + users.availability_note

Revision ID: 0031_sessions
Revises: 0030_flashcards
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_sessions"
down_revision: Union[str, None] = "0030_flashcards"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("availability_note", sa.String(length=255), nullable=True))
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("guest_id", sa.Integer(), nullable=False),
        sa.Column("skill", sa.String(length=255), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("is_trial", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="proposed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["host_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guest_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sessions_host_id", "sessions", ["host_id"])
    op.create_index("ix_sessions_guest_id", "sessions", ["guest_id"])
    op.create_index("ix_sessions_scheduled_at", "sessions", ["scheduled_at"])
    op.create_index("ix_sessions_status", "sessions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sessions_status", table_name="sessions")
    op.drop_index("ix_sessions_scheduled_at", table_name="sessions")
    op.drop_index("ix_sessions_guest_id", table_name="sessions")
    op.drop_index("ix_sessions_host_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_column("users", "availability_note")
