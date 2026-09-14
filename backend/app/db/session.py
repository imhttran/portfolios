"""Async engine and session wiring.

The engine is built lazily from Settings so tests can point DATABASE_URL at a
throwaway database before the first connection is opened.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Importing the models package registers every table on Base.metadata.
import app.models  # noqa: F401
from app.config import get_settings
from app.db.base import Base

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _normalize_url(url: str) -> tuple[str, dict]:
    """Translate a libpq-style URL into one asyncpg understands.

    ``postgres://`` becomes ``postgresql+asyncpg://`` and the libpq-only
    ``sslmode`` parameter is turned into an asyncpg ``ssl`` connect argument.
    """
    parts = urlsplit(url)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    sslmode = query.pop("sslmode", None)
    normalized = urlunsplit(
        (scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )

    connect_args: dict = {}
    if sslmode == "disable":
        connect_args["ssl"] = False
    elif sslmode in ("require", "verify-ca", "verify-full"):
        connect_args["ssl"] = True
    return normalized, connect_args


def build_engine(url: str) -> AsyncEngine:
    normalized, connect_args = _normalize_url(url)
    return create_async_engine(
        normalized,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = build_engine(get_settings().database_url)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding one session per request."""
    async with get_sessionmaker()() as session:
        yield session


async def create_all() -> None:
    """Create any missing tables (idempotent)."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Close pooled connections and drop the cached engine (used by tests)."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
