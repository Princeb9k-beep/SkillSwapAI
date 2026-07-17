"""
Alembic environment — async-aware.

Runs migrations against the async engine using the app's own settings, so
`alembic upgrade head` works both locally (sqlite/aiosqlite) and on Render
(Postgres/asyncpg) without duplicating connection config.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Make the app package importable when Alembic runs from backend/.
from app.config import get_settings  # noqa: E402
from app.database import Base  # noqa: E402
from app import models  # noqa: F401,E402  (import registers all tables on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return get_settings().async_database_url


def run_migrations_offline() -> None:
    """Emit SQL to a script without a live DB connection."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # enables ALTER on sqlite; harmless on Postgres
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations with a live async connection."""
    engine = create_async_engine(_url(), poolclass=None)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
