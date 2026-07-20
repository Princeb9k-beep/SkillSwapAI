"""match signals: learner feedback that improves match ranking (data moat)

Revision ID: 0016_match_signals
Revises: 0015_onboarded
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_match_signals"
down_revision: Union[str, None] = "0015_onboarded"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "match_signals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("partner_id", sa.Integer(), nullable=False),
        sa.Column("signal", sa.String(length=12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["partner_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "partner_id", name="uq_match_signal_pair"),
    )
    op.create_index("ix_match_signals_user_id", "match_signals", ["user_id"])
    op.create_index("ix_match_signals_partner_id", "match_signals", ["partner_id"])
    op.create_index("ix_match_signals_signal", "match_signals", ["signal"])


def downgrade() -> None:
    op.drop_index("ix_match_signals_signal", table_name="match_signals")
    op.drop_index("ix_match_signals_partner_id", table_name="match_signals")
    op.drop_index("ix_match_signals_user_id", table_name="match_signals")
    op.drop_table("match_signals")
