"""learning-buddy shared streaks

Revision ID: 0033_buddies
Revises: 0032_activity_feed
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033_buddies"
down_revision: Union[str, None] = "0032_activity_feed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "buddies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inviter_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="pending"),
        sa.Column("streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inviter_checked_on", sa.Date(), nullable=True),
        sa.Column("partner_checked_on", sa.Date(), nullable=True),
        sa.Column("last_advanced_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["partner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_buddies_inviter_id", "buddies", ["inviter_id"])
    op.create_index("ix_buddies_partner_id", "buddies", ["partner_id"])
    op.create_index("ix_buddies_status", "buddies", ["status"])


def downgrade() -> None:
    op.drop_index("ix_buddies_status", table_name="buddies")
    op.drop_index("ix_buddies_partner_id", table_name="buddies")
    op.drop_index("ix_buddies_inviter_id", table_name="buddies")
    op.drop_table("buddies")
