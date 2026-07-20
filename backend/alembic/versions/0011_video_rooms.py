"""video practice rooms: rooms + participants (spec §2.3)

Revision ID: 0011_video_rooms
Revises: 0010_ai_twin
Create Date: 2026-07-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_video_rooms"
down_revision: Union[str, None] = "0010_ai_twin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "practice_rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("topic", sa.String(length=60), nullable=False, server_default="General"),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["host_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("code", name="uq_practice_room_code"),
    )
    op.create_index("ix_practice_rooms_code", "practice_rooms", ["code"], unique=True)
    op.create_index("ix_practice_rooms_host_id", "practice_rooms", ["host_id"])
    op.create_index("ix_practice_rooms_topic", "practice_rooms", ["topic"])
    op.create_index("ix_practice_rooms_is_open", "practice_rooms", ["is_open"])

    op.create_table(
        "room_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["room_id"], ["practice_rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_room_participants_room_id", "room_participants", ["room_id"])
    op.create_index("ix_room_participants_user_id", "room_participants", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_room_participants_user_id", table_name="room_participants")
    op.drop_index("ix_room_participants_room_id", table_name="room_participants")
    op.drop_table("room_participants")

    op.drop_index("ix_practice_rooms_is_open", table_name="practice_rooms")
    op.drop_index("ix_practice_rooms_topic", table_name="practice_rooms")
    op.drop_index("ix_practice_rooms_host_id", table_name="practice_rooms")
    op.drop_index("ix_practice_rooms_code", table_name="practice_rooms")
    op.drop_table("practice_rooms")
