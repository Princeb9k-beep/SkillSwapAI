"""marketplace: listings + orders (spec §3.7)

Revision ID: 0007_marketplace
Revises: 0006_reputation
Create Date: 2026-07-18

Paid tutoring / courses / templates: listings and orders with commission.
Actual payment capture is left to a future Stripe integration (orders carry a
`paid` flag set by the payment webhook).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_marketplace"
down_revision: Union[str, None] = "0006_reputation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "marketplace_listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="tutoring"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["seller_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_marketplace_listings_seller_id", "marketplace_listings", ["seller_id"])
    op.create_index("ix_marketplace_listings_kind", "marketplace_listings", ["kind"])

    op.create_table(
        "marketplace_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("buyer_id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("commission_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="requested"),
        sa.Column("paid", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["buyer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_marketplace_orders_listing_id", "marketplace_orders", ["listing_id"])
    op.create_index("ix_marketplace_orders_buyer_id", "marketplace_orders", ["buyer_id"])
    op.create_index("ix_marketplace_orders_seller_id", "marketplace_orders", ["seller_id"])
    op.create_index("ix_marketplace_orders_status", "marketplace_orders", ["status"])


def downgrade() -> None:
    for ix in (
        "ix_marketplace_orders_status",
        "ix_marketplace_orders_seller_id",
        "ix_marketplace_orders_buyer_id",
        "ix_marketplace_orders_listing_id",
    ):
        op.drop_index(ix, table_name="marketplace_orders")
    op.drop_table("marketplace_orders")

    op.drop_index("ix_marketplace_listings_kind", table_name="marketplace_listings")
    op.drop_index("ix_marketplace_listings_seller_id", table_name="marketplace_listings")
    op.drop_table("marketplace_listings")
