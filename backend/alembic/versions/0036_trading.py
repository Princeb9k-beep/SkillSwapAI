"""Day-trading platform: accounts, positions, orders, watchlist, journal

Revision ID: 0036_trading
Revises: 0035_user_timezone
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036_trading"
down_revision: Union[str, None] = "0035_user_timezone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trading_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(length=10), nullable=False, server_default="paper"),
        sa.Column("cash", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("risk_per_trade_pct", sa.Float(), nullable=False, server_default="1"),
        sa.Column("max_daily_loss_pct", sa.Float(), nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "mode", name="uq_trading_account_mode"),
    )
    op.create_index("ix_trading_accounts_user_id", "trading_accounts", ["user_id"])
    op.create_index("ix_trading_accounts_mode", "trading_accounts", ["mode"])

    op.create_table(
        "trading_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("trading_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("account_id", "symbol", name="uq_trading_position"),
    )
    op.create_index("ix_trading_positions_account_id", "trading_positions", ["account_id"])
    op.create_index("ix_trading_positions_symbol", "trading_positions", ["symbol"])

    op.create_table(
        "trading_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("trading_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="filled"),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_trading_orders_account_id", "trading_orders", ["account_id"])
    op.create_index("ix_trading_orders_user_id", "trading_orders", ["user_id"])
    op.create_index("ix_trading_orders_symbol", "trading_orders", ["symbol"])
    op.create_index("ix_trading_orders_status", "trading_orders", ["status"])
    op.create_index("ix_trading_orders_created_at", "trading_orders", ["created_at"])

    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "symbol", name="uq_watchlist_symbol"),
    )
    op.create_index("ix_watchlist_user_id", "watchlist", ["user_id"])
    op.create_index("ix_watchlist_symbol", "watchlist", ["symbol"])

    op.create_table(
        "trade_journal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False, server_default="buy"),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("stop_price", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("pnl", sa.Float(), nullable=True),
        sa.Column("thesis", sa.Text(), nullable=True),
        sa.Column("emotion", sa.String(length=40), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("ai_review", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_trade_journal_user_id", "trade_journal", ["user_id"])
    op.create_index("ix_trade_journal_symbol", "trade_journal", ["symbol"])
    op.create_index("ix_trade_journal_created_at", "trade_journal", ["created_at"])


def downgrade() -> None:
    op.drop_table("trade_journal")
    op.drop_table("watchlist")
    op.drop_table("trading_orders")
    op.drop_table("trading_positions")
    op.drop_table("trading_accounts")
