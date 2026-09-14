from collections.abc import AsyncIterator

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from arena_onsale.shared.redis import RedisClient
from arena_onsale.shared.runtime import Runtime


def get_runtime(request: Request) -> Runtime:
    runtime = getattr(request.app.state, "runtime", None)
    if not isinstance(runtime, Runtime):
        raise HTTPException(status_code=503, detail="runtime not ready")
    return runtime


def get_engine(request: Request) -> AsyncEngine:
    return get_runtime(request).engine


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with get_runtime(request).session_factory() as session:
        yield session


def get_redis(request: Request) -> RedisClient:
    return get_runtime(request).redis
