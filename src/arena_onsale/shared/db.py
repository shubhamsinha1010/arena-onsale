"""SQLAlchemy async engine tuned for PgBouncer transaction pooling."""

from typing import TypedDict

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import QueuePool

from arena_onsale.shared.settings import Settings

# PgBouncer transaction pooling rebinds server connections between
# client checkouts. asyncpg prepared statements would leak across clients.
PGBOUNCER_CONNECT_ARGS: dict[str, int] = {"statement_cache_size": 0}


class PoolStats(TypedDict):
    size: int
    checked_in: int
    checked_out: int
    overflow: int


def create_engine(settings: Settings, *, admin: bool = False) -> AsyncEngine:
    """Build an async engine.

    ``statement_cache_size=0`` is mandatory when the DSN points at PgBouncer
    in transaction pooling: prepared statements are bound to connections that
    PgBouncer will hand to someone else.
    """
    url = settings.database_admin_url if admin else settings.database_url
    return create_async_engine(
        url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_pre_ping=True,
        pool_use_lifo=True,
        connect_args=PGBOUNCER_CONNECT_ARGS,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def pool_stats(engine: AsyncEngine) -> PoolStats:
    pool = engine.sync_engine.pool
    if not isinstance(pool, QueuePool):
        return PoolStats(size=0, checked_in=0, checked_out=0, overflow=0)
    return PoolStats(
        size=pool.size(),
        checked_in=pool.checkedin(),
        checked_out=pool.checkedout(),
        overflow=pool.overflow(),
    )
