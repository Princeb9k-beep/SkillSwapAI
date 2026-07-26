"""daily reminders: users.daily_reminder + last_reminded_on

Revision ID: 0026_daily_reminders
Revises: 0025_skill_assessments
Create Date: 2026-07-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_daily_reminders"
down_revision: Union[str, None] = "0025_skill_assessments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("daily_reminder", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("last_reminded_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_reminded_on")
    op.drop_column("users", "daily_reminder")
