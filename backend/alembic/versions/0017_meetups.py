"""local meetups: opt-in study meetups + RSVPs (spec §3.5)

Revision ID: 0017_meetups
Revises: 0016_match_signals
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_meetups"
down_revision: Union[str, None] = "0016_match_signals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meetups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=False, server_default="Online"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["host_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_meetups_host_id", "meetups", ["host_id"])
    op.create_index("ix_meetups_starts_at", "meetups", ["starts_at"])

    op.create_table(
        "meetup_rsvps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("meetup_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["meetup_id"], ["meetups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("meetup_id", "user_id", name="uq_meetup_rsvp"),
    )
    op.create_index("ix_meetup_rsvps_meetup_id", "meetup_rsvps", ["meetup_id"])
    op.create_index("ix_meetup_rsvps_user_id", "meetup_rsvps", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_meetup_rsvps_user_id", table_name="meetup_rsvps")
    op.drop_index("ix_meetup_rsvps_meetup_id", table_name="meetup_rsvps")
    op.drop_table("meetup_rsvps")
    op.drop_index("ix_meetups_starts_at", table_name="meetups")
    op.drop_index("ix_meetups_host_id", table_name="meetups")
    op.drop_table("meetups")
