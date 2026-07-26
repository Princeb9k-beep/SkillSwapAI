"""Lightweight in-process background task runner.

Fire-and-forget coroutines that shouldn't block the HTTP response — sending
email, web-push fan-out, etc. Tasks run on the app's event loop with a bounded
concurrency limit; exceptions are logged, never raised into the request. A
strong reference is kept until each task finishes so it isn't GC'd mid-flight.

This is deliberately process-local (fits the single-service deploy). The same
`run_in_background(...)` call site would later hand off to a Redis/worker queue
without touching callers.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger("skillswap.background")

_MAX_CONCURRENCY = 32
_semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
_tasks: set[asyncio.Task] = set()


async def _guard(coro: Coroutine[Any, Any, Any], name: str) -> None:
    async with _semaphore:
        try:
            await coro
        except Exception:  # noqa: BLE001 — a background failure must not crash anything
            logger.exception("background task %r failed", name)


def run_in_background(coro: Coroutine[Any, Any, Any], *, name: str = "task") -> None:
    """Schedule a coroutine to run without blocking the caller.

    Falls back to synchronous execution only when there's no running loop
    (e.g. certain scripts), so callers never have to care which context they're in.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop running — run it to completion now.
        asyncio.run(_guard(coro, name))
        return
    task = loop.create_task(_guard(coro, name))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:
    """Await all in-flight background tasks (used by tests)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
