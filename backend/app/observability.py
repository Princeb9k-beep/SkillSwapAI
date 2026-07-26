"""Logging + error monitoring setup.

- ``configure_logging`` installs either a plain or JSON log formatter (JSON is
  friendlier to log aggregators in production).
- ``init_sentry`` wires up Sentry error reporting when ``SENTRY_DSN`` is set and
  the SDK is installed; otherwise it's a no-op, so the app runs fine without it.
"""

from __future__ import annotations

import json
import logging
import sys
import time

from .config import get_settings


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("method", "path", "status", "duration_ms"):
            if key in record.__dict__:
                payload[key] = record.__dict__[key]
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    if settings.log_json:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def init_sentry() -> bool:
    """Initialize Sentry if configured. Returns True when active."""
    settings = get_settings()
    if not settings.sentry_dsn.strip():
        return False
    try:
        import sentry_sdk  # noqa: PLC0415
    except ImportError:
        logging.getLogger("skillswap").warning(
            "SENTRY_DSN set but sentry-sdk isn't installed — skipping."
        )
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        environment=settings.app_env,
    )
    logging.getLogger("skillswap").info("Sentry error monitoring enabled")
    return True
