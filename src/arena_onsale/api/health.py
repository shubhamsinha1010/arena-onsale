from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from arena_onsale.api.deps import get_engine, get_redis, get_session
from arena_onsale.shared.db import PoolStats, pool_stats
from arena_onsale.shared.redis import RedisClient

router = APIRouter(tags=["health"])


class LiveResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = "ok"
    postgres: Literal["ok"]
    redis: Literal["ok"]
    pool: PoolStats


@router.get("/health/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse()


@router.get("/health/ready", response_model=ReadyResponse)
async def ready(
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[RedisClient, Depends(get_redis)],
    engine: Annotated[AsyncEngine, Depends(get_engine)],
) -> ReadyResponse:
    try:
        await session.execute(text("SELECT 1"))
        if await redis.ping() is not True:
            raise HTTPException(status_code=503, detail="redis ping failed")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="dependency check failed") from exc
    return ReadyResponse(postgres="ok", redis="ok", pool=pool_stats(engine))
