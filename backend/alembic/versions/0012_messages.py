"""direct messaging: 1:1 messages between users (spec §2.3)

Revision ID: 0012_messages
Revises: 0011_video_rooms
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_messages"
down_revision: Union[str, None] = "0011_video_rooms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])
    op.create_index("ix_messages_recipient_id", "messages", ["recipient_id"])
    op.create_index("ix_messages_read", "messages", ["read"])
    # Fast conversation lookups in both directions.
    op.create_index("ix_messages_pair", "messages", ["sender_id", "recipient_id"])


def downgrade() -> None:
    op.drop_index("ix_messages_pair", table_name="messages")
    op.drop_index("ix_messages_read", table_name="messages")
    op.drop_index("ix_messages_recipient_id", table_name="messages")
    op.drop_index("ix_messages_sender_id", table_name="messages")
    op.drop_table("messages")
