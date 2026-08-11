"""
Market-data layer — provider-agnostic quotes & candles.

The rest of the app never talks to a data vendor directly; it calls `get_quote`
and `get_candles` here, and this module picks a provider from settings:

  * "synthetic" (default) — a deterministic pseudo-random price series seeded by
    the symbol. Needs no API key and no network, so the app boots, demos, and
    tests run fully offline, yet each symbol has a stable, plausible chart.
  * "alpaca" — real stock/crypto bars from Alpaca's data API (one account also
    doubles as the live broker later). Any network/credential failure degrades
    gracefully back to the synthetic series so a feature never hard-fails.

A candle (bar) is a dict: {"t": iso8601, "o", "h", "l", "c", "v"} (floats).
A quote is: {"symbol", "price", "prev_close", "change", "change_pct", "as_of"}.

Bars are cached briefly in Redis (best-effort) to spare the upstream quota.
"""

from __future__ import annotations

import hashlib
import logging
import math
from datetime import datetime, timedelta, timezone

import httpx

from .cache import cache_get, cache_set, make_key
from .config import get_settings

logger = logging.getLogger("skillswap.market")

# Supported bar sizes -> (minutes per bar, Alpaca timeframe string).
TIMEFRAMES: dict[str, tuple[int, str]] = {
    "1m": (1, "1Min"),
    "5m": (5, "5Min"),
    "15m": (15, "15Min"),
    "1h": (60, "1Hour"),
    "1d": (1440, "1Day"),
}

# A small default universe the screener/watchlist can lean on out of the box.
DEFAULT_UNIVERSE: list[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD",
    "NFLX", "JPM", "V", "DIS", "BA", "SPY", "QQQ", "BTC/USD", "ETH/USD",
]

# How long a candle series may be reused before we recompute/refetch.
_CANDLE_TTL_SECONDS = 30


# --------------------------------------------------------------------------- #
# Synthetic provider (deterministic, offline)                                 #
# --------------------------------------------------------------------------- #
def _seed(symbol: str) -> int:
    """A stable integer seed derived from the symbol (so charts don't jump)."""
    digest = hashlib.sha256(symbol.upper().encode()).hexdigest()
    return int(digest[:8], 16)


def _base_price(symbol: str) -> float:
    """A plausible, stable anchor price for a symbol (crypto trades higher)."""
    s = _seed(symbol)
    if "BTC" in symbol.upper():
        return 40000 + (s % 20000)
    if "ETH" in symbol.upper():
        return 2000 + (s % 1500)
    return 20.0 + (s % 400)  # $20 – $420


def _synthetic_candles(symbol: str, timeframe: str, limit: int) -> list[dict]:
    """A deterministic OHLCV walk: reproducible per (symbol, bar, calendar day)."""
    minutes, _ = TIMEFRAMES.get(timeframe, TIMEFRAMES["1d"])
    limit = max(2, min(limit, 500))
    # Reseed each day so the series evolves slowly over time but is stable intraday.
    day_ord = datetime.now(timezone.utc).date().toordinal()
    rng_state = (_seed(symbol) ^ (day_ord * 2654435761)) & 0xFFFFFFFF

    def _next() -> float:
        # xorshift32 -> uniform in [0, 1)
        nonlocal rng_state
        x = rng_state or 1
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        rng_state = x & 0xFFFFFFFF
        return rng_state / 0xFFFFFFFF

    anchor = _base_price(symbol)
    # Volatility scales with price and bar size.
    vol = anchor * 0.004 * math.sqrt(minutes / 5 + 1)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    bars: list[dict] = []
    price = anchor
    for i in range(limit):
        t = now - timedelta(minutes=minutes * (limit - 1 - i))
        drift = (_next() - 0.48) * vol       # slight upward bias
        o = price
        c = max(0.5, o + drift)
        wick = abs(drift) + _next() * vol * 0.6
        h = max(o, c) + wick * _next()
        low = min(o, c) - wick * _next()
        v = round(10_000 + _next() * 90_000)
        bars.append({
            "t": t.isoformat(),
            "o": round(o, 2), "h": round(h, 2),
            "l": round(max(0.1, low), 2), "c": round(c, 2), "v": v,
        })
        price = c
    return bars


# --------------------------------------------------------------------------- #
# Alpaca provider (real data; best-effort)                                    #
# --------------------------------------------------------------------------- #
async def _alpaca_candles(symbol: str, timeframe: str, limit: int) -> list[dict] | None:
    settings = get_settings()
    if not (settings.alpaca_api_key and settings.alpaca_api_secret):
        return None
    _, tf = TIMEFRAMES.get(timeframe, TIMEFRAMES["1d"])
    is_crypto = "/" in symbol
    if is_crypto:
        url = f"{settings.alpaca_data_url}/v1beta3/crypto/us/bars"
        params = {"symbols": symbol, "timeframe": tf, "limit": limit}
    else:
        url = f"{settings.alpaca_data_url}/v2/stocks/{symbol}/bars"
        params = {"timeframe": tf, "limit": limit, "adjustment": "raw"}
    headers = {
        "APCA-API-KEY-ID": settings.alpaca_api_key,
        "APCA-API-SECRET-KEY": settings.alpaca_api_secret,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as http:
            resp = await http.get(url, params=params, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:  # noqa: BLE001 - degrade to synthetic
        logger.warning("Alpaca bars failed for %s: %s", symbol, exc)
        return None

    raw = payload.get("bars")
    if isinstance(raw, dict):  # crypto shape: {"BTC/USD": [...]}
        raw = raw.get(symbol, [])
    if not raw:
        return None
    return [
        {
            "t": b.get("t"),
            "o": float(b.get("o", 0)), "h": float(b.get("h", 0)),
            "l": float(b.get("l", 0)), "c": float(b.get("c", 0)),
            "v": float(b.get("v", 0)),
        }
        for b in raw
    ]


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
async def get_candles(symbol: str, timeframe: str = "1d", limit: int = 120) -> list[dict]:
    """Return recent OHLCV bars for `symbol`, oldest first. Never raises."""
    symbol = symbol.strip().upper()
    timeframe = timeframe if timeframe in TIMEFRAMES else "1d"
    key = make_key("bars", get_settings().market_data_provider, symbol, timeframe, limit)
    cached = await cache_get(key)
    if cached:
        return cached

    bars: list[dict] | None = None
    if get_settings().market_data_provider == "alpaca":
        bars = await _alpaca_candles(symbol, timeframe, limit)
    if not bars:
        bars = _synthetic_candles(symbol, timeframe, limit)

    await cache_set(key, bars, ttl=_CANDLE_TTL_SECONDS)
    return bars


async def get_quote(symbol: str) -> dict:
    """Return a lightweight quote derived from the two most recent bars."""
    symbol = symbol.strip().upper()
    bars = await get_candles(symbol, "1d", 2)
    last = bars[-1]["c"] if bars else _base_price(symbol)
    prev = bars[-2]["c"] if len(bars) >= 2 else last
    change = round(last - prev, 4)
    change_pct = round((change / prev) * 100, 2) if prev else 0.0
    return {
        "symbol": symbol,
        "price": round(last, 2),
        "prev_close": round(prev, 2),
        "change": change,
        "change_pct": change_pct,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


async def get_quotes(symbols: list[str]) -> list[dict]:
    """Quotes for many symbols (sequential; the synthetic path is cheap)."""
    out: list[dict] = []
    for sym in symbols:
        try:
            out.append(await get_quote(sym))
        except Exception:  # noqa: BLE001
            continue
    return out
