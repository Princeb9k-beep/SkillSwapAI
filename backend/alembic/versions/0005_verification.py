"""skill verification: requests + peer reviews + verified flag

Revision ID: 0005_verification
Revises: 0004_communities
Create Date: 2026-07-18

Peer-reviewed skill verification (spec §2.5): a `verified` flag on skills plus
verification_requests and verification_reviews.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_verification"
down_revision: Union[str, None] = "0004_communities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skills",
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="0"),
    )

    op.create_table(
        "verification_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("skill_name", sa.String(length=255), nullable=False),
        sa.Column("skill_normalized", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("evidence_url", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("approvals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_verification_requests_user_id", "verification_requests", ["user_id"])
    op.create_index("ix_verification_requests_status", "verification_requests", ["status"])
    op.create_index(
        "ix_verification_requests_skill_normalized", "verification_requests", ["skill_normalized"]
    )

    op.create_table(
        "verification_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("vote", sa.String(length=10), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["request_id"], ["verification_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("request_id", "reviewer_id", name="uq_review"),
    )
    op.create_index("ix_verification_reviews_request_id", "verification_reviews", ["request_id"])
    op.create_index("ix_verification_reviews_reviewer_id", "verification_reviews", ["reviewer_id"])


def downgrade() -> None:
    op.drop_index("ix_verification_reviews_reviewer_id", table_name="verification_reviews")
    op.drop_index("ix_verification_reviews_request_id", table_name="verification_reviews")
    op.drop_table("verification_reviews")

    op.drop_index("ix_verification_requests_skill_normalized", table_name="verification_requests")
    op.drop_index("ix_verification_requests_status", table_name="verification_requests")
    op.drop_index("ix_verification_requests_user_id", table_name="verification_requests")
    op.drop_table("verification_requests")

    op.drop_column("skills", "verified")
