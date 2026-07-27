"""certificates + peer endorsements

Revision ID: 0034_certificates_endorsements
Revises: 0033_buddies
Create Date: 2026-07-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034_certificates_endorsements"
down_revision: Union[str, None] = "0033_buddies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("path_slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "path_slug", name="uq_certificate_course"),
    )
    op.create_index("ix_certificates_user_id", "certificates", ["user_id"])
    op.create_index("ix_certificates_path_slug", "certificates", ["path_slug"])
    op.create_index("ix_certificates_code", "certificates", ["code"], unique=True)

    op.create_table(
        "endorsements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("endorser_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("skill", sa.String(length=255), nullable=False),
        sa.Column("skill_normalized", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["endorser_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("endorser_id", "subject_id", "skill_normalized", name="uq_endorsement"),
    )
    op.create_index("ix_endorsements_endorser_id", "endorsements", ["endorser_id"])
    op.create_index("ix_endorsements_subject_id", "endorsements", ["subject_id"])
    op.create_index("ix_endorsements_skill_normalized", "endorsements", ["skill_normalized"])


def downgrade() -> None:
    op.drop_index("ix_endorsements_skill_normalized", table_name="endorsements")
    op.drop_index("ix_endorsements_subject_id", table_name="endorsements")
    op.drop_index("ix_endorsements_endorser_id", table_name="endorsements")
    op.drop_table("endorsements")
    op.drop_index("ix_certificates_code", table_name="certificates")
    op.drop_index("ix_certificates_path_slug", table_name="certificates")
    op.drop_index("ix_certificates_user_id", table_name="certificates")
    op.drop_table("certificates")
