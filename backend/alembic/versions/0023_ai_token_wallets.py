"""ai token wallets: replace the daily AI counter with a monthly token wallet

Revision ID: 0023_ai_token_wallets
Revises: 0022_subscription_tiers
Create Date: 2026-07-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_ai_token_wallets"
down_revision: Union[str, None] = "0022_subscription_tiers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_wallets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False, server_default=""),
        sa.Column("allowance_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("purchased", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_ai_wallets_user"),
    )
    op.create_index("ix_ai_wallets_user_id", "ai_wallets", ["user_id"])

    # The daily counter is superseded by the token wallet.
    op.drop_index("ix_ai_usage_day", table_name="ai_usage")
    op.drop_index("ix_ai_usage_user_id", table_name="ai_usage")
    op.drop_table("ai_usage")


def downgrade() -> None:
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

    op.drop_index("ix_ai_wallets_user_id", table_name="ai_wallets")
    op.drop_table("ai_wallets")
