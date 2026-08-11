"""
Broker abstraction — one order interface, swappable execution behind it.

`Broker` is the contract the trading router calls. Two implementations satisfy it:

  * PaperBroker — settles market orders against the in-app `TradingAccount`
    ledger (virtual cash + positions). Ships now; every user starts here.
  * LiveBroker  — routes to a real broker (Alpaca). It stays inert unless
    LIVE_TRADING_ENABLED is true AND credentials are present, so real money is
    always a deliberate, gated opt-in — never the default path.

`select_broker(settings)` returns the right one. Because both honor the same
interface and the same `TradingAccount`, the order-ticket UI and endpoints don't
change when a user graduates from paper to live.

Money note: the paper ledger uses floats (fractional share prices), which is fine
for a simulator; a real-money ledger would move to integer minor units.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .market_data import get_quote
from .models import TradingAccount, TradingOrder, TradingPosition


class OrderError(Exception):
    """A rejected order carrying a user-safe message (insufficient funds, etc.)."""


@dataclass
class Fill:
    order: TradingOrder
    position: TradingPosition | None


async def get_or_create_account(
    session: AsyncSession, user_id: int, *, starting_cash: float, mode: str = "paper"
) -> TradingAccount:
    """Fetch the user's account for `mode`, creating a funded paper one if absent."""
    result = await session.execute(
        select(TradingAccount).where(
            TradingAccount.user_id == user_id, TradingAccount.mode == mode
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        account = TradingAccount(
            user_id=user_id,
            mode=mode,
            cash=starting_cash if mode == "paper" else 0.0,
        )
        session.add(account)
        await session.flush()
    return account


async def positions_for(session: AsyncSession, account_id: int) -> list[TradingPosition]:
    result = await session.execute(
        select(TradingPosition).where(TradingPosition.account_id == account_id)
    )
    return list(result.scalars().all())


async def _today_realized_pnl(session: AsyncSession, account_id: int) -> float:
    """Sum of realized P&L on orders filled today (drives the daily-loss lock)."""
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(TradingOrder.realized_pnl).where(
            TradingOrder.account_id == account_id,
            TradingOrder.created_at >= start,
            TradingOrder.realized_pnl.is_not(None),
        )
    )
    return round(sum(v for (v,) in result.all() if v is not None), 2)


class Broker:
    """The order interface the app depends on."""

    async def place_order(
        self, session: AsyncSession, account: TradingAccount,
        symbol: str, side: str, quantity: float, note: str | None = None,
    ) -> Fill:
        raise NotImplementedError


class PaperBroker(Broker):
    """Fills market orders immediately at the live quote against virtual cash."""

    async def place_order(
        self, session: AsyncSession, account: TradingAccount,
        symbol: str, side: str, quantity: float, note: str | None = None,
    ) -> Fill:
        symbol = symbol.strip().upper()
        side = side.lower()
        if side not in {"buy", "sell"}:
            raise OrderError("Side must be 'buy' or 'sell'.")
        if quantity <= 0:
            raise OrderError("Quantity must be greater than zero.")
        if account.locked:
            raise OrderError(
                "Account is locked for the day: your daily loss limit was hit. "
                "Step away and reset tomorrow — that's the guardrail working."
            )

        quote = await get_quote(symbol)
        price = float(quote["price"])
        if price <= 0:
            raise OrderError(f"No live price available for {symbol}.")

        # Load the current position for this symbol (if any).
        result = await session.execute(
            select(TradingPosition).where(
                TradingPosition.account_id == account.id,
                TradingPosition.symbol == symbol,
            )
        )
        position = result.scalar_one_or_none()
        realized: float | None = None

        if side == "buy":
            cost = price * quantity
            if cost > account.cash + 1e-9:
                raise OrderError(
                    f"Insufficient buying power: need ${cost:,.2f}, have ${account.cash:,.2f}."
                )
            account.cash = round(account.cash - cost, 4)
            if position is None:
                position = TradingPosition(
                    account_id=account.id, symbol=symbol,
                    quantity=quantity, avg_price=price,
                )
                session.add(position)
            else:
                total_qty = position.quantity + quantity
                position.avg_price = round(
                    (position.avg_price * position.quantity + price * quantity) / total_qty, 4
                )
                position.quantity = round(total_qty, 6)
        else:  # sell (long-only MVP: can't sell more than held)
            held = position.quantity if position else 0.0
            if quantity > held + 1e-9:
                raise OrderError(
                    f"You hold {held:g} {symbol}; can't sell {quantity:g}. "
                    "(Short selling isn't enabled yet.)"
                )
            proceeds = price * quantity
            realized = round((price - position.avg_price) * quantity, 4)
            account.cash = round(account.cash + proceeds, 4)
            position.quantity = round(position.quantity - quantity, 6)
            if position.quantity <= 1e-9:
                await session.delete(position)
                position = None

        order = TradingOrder(
            account_id=account.id, user_id=account.user_id, symbol=symbol,
            side=side, quantity=quantity, price=price, status="filled",
            realized_pnl=realized, note=note,
        )
        session.add(order)
        await session.flush()

        # Daily-loss guardrail: lock the account once today's realized loss
        # exceeds the configured % of equity.
        day_pnl = await _today_realized_pnl(session, account.id)
        equity = account.cash  # positions are marked at cost; cash-based bound is conservative
        if equity > 0 and day_pnl < 0 and abs(day_pnl) >= equity * (account.max_daily_loss_pct / 100):
            account.locked = True

        return Fill(order=order, position=position)


class LiveBroker(Broker):
    """Placeholder for real-broker routing (Alpaca). Deliberately not wired to
    send real orders yet — enabling it is a separate, reviewed step. Until then
    it refuses clearly rather than silently paper-trading real intent."""

    async def place_order(
        self, session: AsyncSession, account: TradingAccount,
        symbol: str, side: str, quantity: float, note: str | None = None,
    ) -> Fill:
        raise OrderError(
            "Live trading isn't connected yet. Connect a broker and enable live "
            "mode to route real orders; until then, use the paper account."
        )


def select_broker(settings: Settings, mode: str = "paper") -> Broker:
    """Pick the broker for the requested mode, honoring the live-trading gate."""
    if mode == "live" and settings.live_trading_enabled:
        return LiveBroker()
    return PaperBroker()
