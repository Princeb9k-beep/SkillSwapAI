"""subscription tiers: user.tier + daily AI usage counter

Revision ID: 0022_subscription_tiers
Revises: 0021_skill_academy
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_subscription_tiers"
down_revision: Union[str, None] = "0021_skill_academy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("tier", sa.String(length=10), nullable=False, server_default="free"),
    )
    op.create_index("ix_users_tier", "users", ["tier"])

    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "day", name="uq_ai_usage_day"),
    )
    op.create_index("ix_ai_usage_user_id", "ai_usage", ["user_id"])
    op.create_index("ix_ai_usage_day", "ai_usage", ["day"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_day", table_name="ai_usage")
    op.drop_index("ix_ai_usage_user_id", table_name="ai_usage")
    op.drop_table("ai_usage")
    op.drop_index("ix_users_tier", table_name="users")
    op.drop_column("users", "tier")
