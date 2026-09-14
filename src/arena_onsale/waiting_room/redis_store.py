from arena_onsale.shared.redis import RedisClient
from arena_onsale.waiting_room.keys import (
    QUEUE_KEY,
    SEQ_KEY,
    SHOPPERS_KEY,
    rate_key,
    token_key,
    visitor_key,
)
from arena_onsale.waiting_room.store import Shopper


class RedisWaitingRoomStore:
    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def next_score(self) -> float:
        return float(await self._redis.incr(SEQ_KEY))

    async def enqueue(self, visitor_id: str, score: float) -> bool:
        added = await self._redis.zadd(QUEUE_KEY, {visitor_id: score}, nx=True)
        return added == 1 if isinstance(added, int) else False

    async def rank(self, visitor_id: str) -> int | None:
        rank = await self._redis.zrank(QUEUE_KEY, visitor_id)
        return rank if isinstance(rank, int) else None

    async def queue_size(self) -> int:
        return int(await self._redis.zcard(QUEUE_KEY))

    async def pop_front(self, n: int) -> list[str]:
        if n <= 0:
            return []
        popped = await self._redis.zpopmin(QUEUE_KEY, n)
        members: list[str] = []
        for item in popped:
            if isinstance(item, tuple):
                members.append(str(item[0]))
            else:
                members.append(str(item))
        return members

    async def put_shopper(self, shopper: Shopper, ttl_seconds: int) -> None:
        pipe = self._redis.pipeline()
        pipe.set(token_key(shopper.token), shopper.visitor_id, ex=ttl_seconds)
        pipe.set(visitor_key(shopper.visitor_id), shopper.token, ex=ttl_seconds)
        pipe.zadd(SHOPPERS_KEY, {shopper.visitor_id: shopper.expires_at})
        await pipe.execute()

    async def get_shopper(self, visitor_id: str) -> Shopper | None:
        token = await self._redis.get(visitor_key(visitor_id))
        if token is None:
            return None
        score = await self._redis.zscore(SHOPPERS_KEY, visitor_id)
        expires_at = 0.0 if score is None else float(score)
        return Shopper(visitor_id=visitor_id, token=str(token), expires_at=expires_at)

    async def visitor_for_token(self, token: str) -> str | None:
        value = await self._redis.get(token_key(token))
        return None if value is None else str(value)

    async def gc_shoppers(self, now: float) -> None:
        await self._redis.zremrangebyscore(SHOPPERS_KEY, "-inf", now)

    async def shopper_count(self, now: float) -> int:
        return int(await self._redis.zcount(SHOPPERS_KEY, now, "+inf"))

    async def take_rate_tokens(self, epoch_second: int, limit: int, wanted: int) -> int:
        if wanted <= 0 or limit <= 0:
            return 0
        key = rate_key(epoch_second)
        current = int(await self._redis.incrby(key, wanted))
        if current == wanted:
            await self._redis.expire(key, 2)
        if current <= limit:
            return wanted
        overflow = current - limit
        granted = max(0, wanted - overflow)
        await self._redis.incrby(key, -overflow)
        return granted
