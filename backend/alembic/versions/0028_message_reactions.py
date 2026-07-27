"""message reactions: messages.reaction

Revision ID: 0028_message_reactions
Revises: 0027_refresh_tokens
Create Date: 2026-07-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028_message_reactions"
down_revision: Union[str, None] = "0027_refresh_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("reaction", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "reaction")
