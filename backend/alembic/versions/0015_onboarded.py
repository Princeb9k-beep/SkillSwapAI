"""onboarding: track whether a user finished first-run onboarding

Revision ID: 0015_onboarded
Revises: 0014_push_subscriptions
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_onboarded"
down_revision: Union[str, None] = "0014_push_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("onboarded", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "onboarded")
