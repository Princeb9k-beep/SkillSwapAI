"""
Async SQLAlchemy setup.

Exposes the declarative `Base`, a lazily-created async engine, and a session
factory. Everything is async end-to-end (asyncpg for Postgres, aiosqlite for the
local test fallback).
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Create (once) and return the async engine."""
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.async_database_url,
            echo=settings.app_debug,
            pool_pre_ping=True,   # drop dead connections instead of erroring
            future=True,
        )
        _sessionmaker = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a session and always closes it."""
    async with get_sessionmaker()() as session:
        yield session


async def dispose_engine() -> None:
    """Close the engine on shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
