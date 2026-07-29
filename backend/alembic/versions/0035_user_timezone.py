"""users.timezone (IANA) for localized session/reminder times

Revision ID: 0035_user_timezone
Revises: 0034_certificates_endorsements
Create Date: 2026-07-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035_user_timezone"
down_revision: Union[str, None] = "0034_certificates_endorsements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
    )


def downgrade() -> None:
    op.drop_column("users", "timezone")
