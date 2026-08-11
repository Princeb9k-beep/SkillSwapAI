"""
Trading Academy — a compact, opinionated curriculum for new day traders.

Static content (no AI needed) that pairs with the paper simulator: each lesson
teaches one idea the beginner can immediately practice on the chart + order
ticket. Ordered from "don't blow up" fundamentals to reading a chart to building
a repeatable process. The AI Coach (trade_ai.review_trade) grades their actual
trades against these ideas.
"""

from __future__ import annotations

CURRICULUM: list[dict] = [
    {
        "slug": "risk-first",
        "title": "Risk First: How Not to Blow Up",
        "level": "beginner",
        "minutes": 8,
        "summary": "The one skill that keeps you in the game longer than everyone else.",
        "lessons": [
            {"key": "position-sizing", "title": "Position sizing & the 1% rule",
             "body": "Never risk more than a small, fixed % (start at 1%) of your account "
                     "on a single trade. Use the Position Sizer: enter your entry and stop, "
                     "and it tells you exactly how many shares keeps your loss capped."},
            {"key": "stops", "title": "Always define your stop before you enter",
             "body": "Your stop is where your thesis is wrong. Decide it before the trade, "
                     "not after — moving a stop to avoid a loss is how small losses become "
                     "account-ending ones."},
            {"key": "daily-loss", "title": "The daily loss limit",
             "body": "Set a max you're willing to lose in a day; when you hit it, you stop. "
                     "The simulator enforces this by locking the account — that discipline is "
                     "the guardrail, not a bug."},
        ],
    },
    {
        "slug": "read-the-chart",
        "title": "Reading the Chart",
        "level": "beginner",
        "minutes": 12,
        "summary": "Candles, trend, and the levels that actually matter.",
        "lessons": [
            {"key": "candles", "title": "What a candlestick tells you",
             "body": "Each candle is open/high/low/close for a period. The body shows who won "
                     "(buyers or sellers); the wicks show the fight. Green closes above open, "
                     "red closes below."},
            {"key": "trend", "title": "Trend: the moving averages",
             "body": "When the 20-day average is above the 50-day and price is above both, "
                     "you're in an uptrend — trade with it, not against it. The analysis panel "
                     "labels the trend for every symbol."},
            {"key": "levels", "title": "Support & resistance",
             "body": "Support is where buyers keep stepping in; resistance is where sellers do. "
                     "The analysis panel marks the nearest of each — great spots for entries "
                     "and stops."},
        ],
    },
    {
        "slug": "momentum",
        "title": "Momentum & Timing",
        "level": "intermediate",
        "minutes": 10,
        "summary": "RSI and MACD — measuring strength and turns.",
        "lessons": [
            {"key": "rsi", "title": "RSI: overbought & oversold",
             "body": "RSI above 70 is stretched (overbought); below 30 is beaten down "
                     "(oversold). Extremes aren't automatic signals — they're context for the "
                     "trend you already identified."},
            {"key": "macd", "title": "MACD: momentum shifts",
             "body": "When the MACD histogram flips positive, short-term momentum is turning "
                     "up; negative, down. Combine it with trend for higher-quality entries."},
        ],
    },
    {
        "slug": "the-process",
        "title": "Building a Repeatable Process",
        "level": "intermediate",
        "minutes": 10,
        "summary": "Journaling, reviewing, and improving like a professional.",
        "lessons": [
            {"key": "thesis", "title": "Write your thesis before you click buy",
             "body": "One sentence: why this, why now, and where you're wrong. If you can't "
                     "write it, you don't have a trade."},
            {"key": "journal", "title": "Journal every trade",
             "body": "Log entry, stop, exit, size, and how you felt. Patterns in your losses "
                     "(revenge trades, oversizing, no stop) show up fast once they're written "
                     "down."},
            {"key": "review", "title": "Let the AI Coach review you",
             "body": "The coach reviews your journalled trades for process — not whether the "
                     "pick was right, but whether you followed your own rules."},
        ],
    },
]
