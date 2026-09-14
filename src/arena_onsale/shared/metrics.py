from prometheus_client import CollectorRegistry, Gauge, generate_latest
from sqlalchemy.ext.asyncio import AsyncEngine

from arena_onsale.shared.db import pool_stats

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


class PoolCollector:
    """Pool gauges live on a per-runtime registry so tests do not clash."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self._size = Gauge(
            "arena_db_pool_size",
            "Configured SQLAlchemy pool size",
            registry=self.registry,
        )
        self._checked_in = Gauge(
            "arena_db_pool_checked_in",
            "Idle connections sitting in the app pool",
            registry=self.registry,
        )
        self._checked_out = Gauge(
            "arena_db_pool_checked_out",
            "Connections currently borrowed by requests",
            registry=self.registry,
        )
        self._overflow = Gauge(
            "arena_db_pool_overflow",
            "Overflow connections above pool_size",
            registry=self.registry,
        )

    def observe(self, engine: AsyncEngine) -> None:
        stats = pool_stats(engine)
        self._size.set(stats["size"])
        self._checked_in.set(stats["checked_in"])
        self._checked_out.set(stats["checked_out"])
        self._overflow.set(stats["overflow"])


def render_metrics(collector: PoolCollector, engine: AsyncEngine) -> bytes:
    collector.observe(engine)
    return generate_latest(collector.registry)
