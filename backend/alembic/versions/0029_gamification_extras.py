"""gamification: streak freezes, daily goal + day xp, weekly league xp

Revision ID: 0029_gamification_extras
Revises: 0028_message_reactions
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_gamification_extras"
down_revision: Union[str, None] = "0028_message_reactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("streak_freezes", sa.Integer(), nullable=False, server_default="2"))
    op.add_column("users", sa.Column("daily_goal", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("users", sa.Column("day_xp", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("day_xp_on", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("week_xp", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("week_key", sa.String(length=8), nullable=True))
    op.create_index("ix_users_week_xp", "users", ["week_xp"])
    op.create_index("ix_users_week_key", "users", ["week_key"])


def downgrade() -> None:
    op.drop_index("ix_users_week_key", table_name="users")
    op.drop_index("ix_users_week_xp", table_name="users")
    op.drop_column("users", "week_key")
    op.drop_column("users", "week_xp")
    op.drop_column("users", "day_xp_on")
    op.drop_column("users", "day_xp")
    op.drop_column("users", "daily_goal")
    op.drop_column("users", "streak_freezes")
