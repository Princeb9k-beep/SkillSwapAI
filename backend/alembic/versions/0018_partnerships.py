"""company partnerships: companies, challenges, submissions (spec §3.10)

Revision ID: 0018_partnerships
Revises: 0017_meetups
Create Date: 2026-07-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_partnerships"
down_revision: Union[str, None] = "0017_meetups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("website", sa.String(length=300), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_companies_created_by", "companies", ["created_by"])

    op.create_table(
        "company_challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="challenge"),
        sa.Column("reward", sa.String(length=200), nullable=True),
        sa.Column("deadline", sa.String(length=60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_company_challenges_company_id", "company_challenges", ["company_id"])
    op.create_index("ix_company_challenges_kind", "company_challenges", ["kind"])

    op.create_table(
        "challenge_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="submitted"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["challenge_id"], ["company_challenges.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("challenge_id", "user_id", name="uq_challenge_submission"),
    )
    op.create_index("ix_challenge_submissions_challenge_id", "challenge_submissions", ["challenge_id"])
    op.create_index("ix_challenge_submissions_user_id", "challenge_submissions", ["user_id"])
    op.create_index("ix_challenge_submissions_status", "challenge_submissions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_challenge_submissions_status", table_name="challenge_submissions")
    op.drop_index("ix_challenge_submissions_user_id", table_name="challenge_submissions")
    op.drop_index("ix_challenge_submissions_challenge_id", table_name="challenge_submissions")
    op.drop_table("challenge_submissions")
    op.drop_index("ix_company_challenges_kind", table_name="company_challenges")
    op.drop_index("ix_company_challenges_company_id", table_name="company_challenges")
    op.drop_table("company_challenges")
    op.drop_index("ix_companies_created_by", table_name="companies")
    op.drop_table("companies")
