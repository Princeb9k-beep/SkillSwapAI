"""Timezone-aware datetime formatting for user-facing text (emails, notifications).

Times are stored in UTC; this renders them in a user's IANA timezone. Falls back
to UTC for missing/invalid zones so it never raises.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _zone(tz: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz) if tz else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return ZoneInfo("UTC")


def fmt_local(dt: datetime, tz: str | None) -> str:
    """Format a datetime in the given timezone, e.g. 'Mon Jan 05, 3:00 PM EST'."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(_zone(tz))
    # %-I isn't portable; strip a leading zero from %I manually.
    stamp = local.strftime("%a %b %d, %I:%M %p %Z")
    return stamp.replace(", 0", ", ")
