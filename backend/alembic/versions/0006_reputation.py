"""reputation reviews (spec §3.6)

Revision ID: 0006_reputation
Revises: 0005_verification
Create Date: 2026-07-18

Multi-dimensional peer reviews used to compute a weighted reputation score.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_reputation"
down_revision: Union[str, None] = "0005_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reputation_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("teaching_quality", sa.Integer(), nullable=False),
        sa.Column("reliability", sa.Integer(), nullable=False),
        sa.Column("response_time", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["subject_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_reputation_reviews_subject_id", "reputation_reviews", ["subject_id"])
    op.create_index("ix_reputation_reviews_reviewer_id", "reputation_reviews", ["reviewer_id"])


def downgrade() -> None:
    op.drop_index("ix_reputation_reviews_reviewer_id", table_name="reputation_reviews")
    op.drop_index("ix_reputation_reviews_subject_id", table_name="reputation_reviews")
    op.drop_table("reputation_reviews")
