from redis.asyncio import Redis

from arena_onsale.shared.settings import Settings

type RedisClient = Redis


def create_redis(settings: Settings) -> RedisClient:
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        health_check_interval=15,
    )
