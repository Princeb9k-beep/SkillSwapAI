"""communities: groups, members, posts

Revision ID: 0004_communities
Revises: 0003_gamification
Create Date: 2026-07-18

Adds topic-based communities with membership and posts (spec §3.4).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_communities"
down_revision: Union[str, None] = "0003_gamification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "communities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("name_normalized", sa.String(length=120), nullable=False),
        sa.Column("topic", sa.String(length=60), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_communities_name_normalized", "communities", ["name_normalized"], unique=True)
    op.create_index("ix_communities_topic", "communities", ["topic"])

    op.create_table(
        "community_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("community_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["community_id"], ["communities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("community_id", "user_id", name="uq_member"),
    )
    op.create_index("ix_community_members_community_id", "community_members", ["community_id"])
    op.create_index("ix_community_members_user_id", "community_members", ["user_id"])

    op.create_table(
        "community_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("community_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["community_id"], ["communities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_community_posts_community_id", "community_posts", ["community_id"])
    op.create_index("ix_community_posts_user_id", "community_posts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_community_posts_user_id", table_name="community_posts")
    op.drop_index("ix_community_posts_community_id", table_name="community_posts")
    op.drop_table("community_posts")

    op.drop_index("ix_community_members_user_id", table_name="community_members")
    op.drop_index("ix_community_members_community_id", table_name="community_members")
    op.drop_table("community_members")

    op.drop_index("ix_communities_topic", table_name="communities")
    op.drop_index("ix_communities_name_normalized", table_name="communities")
    op.drop_table("communities")
