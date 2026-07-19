"""add skill kind + normalized name for AI skill matching

Revision ID: 0002_skill_kind
Revises: 0001_initial
Create Date: 2026-07-18

Adds `kind` ("have"/"want") and `name_normalized` to skills so the matching
engine can join a user's wanted skills against other users' owned skills.
Backfills `name_normalized` from existing rows.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_skill_kind"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skills",
        sa.Column("kind", sa.String(length=10), nullable=False, server_default="have"),
    )
    op.add_column(
        "skills",
        sa.Column(
            "name_normalized", sa.String(length=255), nullable=False, server_default=""
        ),
    )
    # Backfill normalized names for any pre-existing rows.
    op.execute("UPDATE skills SET name_normalized = lower(trim(name))")
    op.create_index("ix_skills_kind", "skills", ["kind"])
    op.create_index("ix_skills_name_normalized", "skills", ["name_normalized"])


def downgrade() -> None:
    op.drop_index("ix_skills_name_normalized", table_name="skills")
    op.drop_index("ix_skills_kind", table_name="skills")
    op.drop_column("skills", "name_normalized")
    op.drop_column("skills", "kind")
