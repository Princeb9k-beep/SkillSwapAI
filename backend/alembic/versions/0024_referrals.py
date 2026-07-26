"""referrals: users.referral_code + users.referred_by_id

Revision ID: 0024_referrals
Revises: 0023_ai_token_wallets
Create Date: 2026-07-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_referrals"
down_revision: Union[str, None] = "0023_ai_token_wallets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("referral_code", sa.String(length=12), nullable=True))
    op.add_column("users", sa.Column("referred_by_id", sa.Integer(), nullable=True))
    op.create_index("ix_users_referral_code", "users", ["referral_code"], unique=True)
    op.create_index("ix_users_referred_by_id", "users", ["referred_by_id"])
    # SQLite can't ADD a constraint to an existing table; the FK is only needed on
    # the real Postgres deployment (the ORM enforces the relationship regardless).
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_users_referred_by",
            "users",
            "users",
            ["referred_by_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_users_referred_by", "users", type_="foreignkey")
    op.drop_index("ix_users_referred_by_id", table_name="users")
    op.drop_index("ix_users_referral_code", table_name="users")
    op.drop_column("users", "referred_by_id")
    op.drop_column("users", "referral_code")
