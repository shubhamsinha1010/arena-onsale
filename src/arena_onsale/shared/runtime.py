from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from arena_onsale.shared.clock import Clock, SystemClock
from arena_onsale.shared.db import create_engine, create_session_factory
from arena_onsale.shared.metrics import PoolCollector
from arena_onsale.shared.redis import RedisClient, create_redis
from arena_onsale.shared.settings import Settings


@dataclass
class Runtime:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    redis: RedisClient
    clock: Clock
    pool_collector: PoolCollector

    async def aclose(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()


def build_runtime(settings: Settings) -> Runtime:
    engine = create_engine(settings)
    return Runtime(
        settings=settings,
        engine=engine,
        session_factory=create_session_factory(engine),
        redis=create_redis(settings),
        clock=SystemClock(),
        pool_collector=PoolCollector(),
    )
