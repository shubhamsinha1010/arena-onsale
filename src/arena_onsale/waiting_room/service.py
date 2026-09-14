import secrets
from datetime import UTC, datetime
from typing import Protocol

from arena_onsale.shared.clock import Clock
from arena_onsale.shared.settings import Settings
from arena_onsale.waiting_room.keys import admits_per_second
from arena_onsale.waiting_room.store import Shopper, WaitingRoomStore


class TokenFactory(Protocol):
    def new_token(self) -> str: ...


class SecretsTokenFactory:
    def new_token(self) -> str:
        return secrets.token_urlsafe(24)


class WaitingRoomService:
    def __init__(
        self,
        store: WaitingRoomStore,
        clock: Clock,
        settings: Settings,
        tokens: TokenFactory | None = None,
    ) -> None:
        self._store = store
        self._clock = clock
        self._settings = settings
        self._tokens = tokens or SecretsTokenFactory()

    async def join(self, visitor_id: str) -> dict[str, object]:
        visitor_id = visitor_id.strip()
        if not visitor_id:
            msg = "visitor_id is required"
            raise ValueError(msg)
        current = await self.status(visitor_id)
        if current["state"] != "unknown":
            return current
        score = await self._store.next_score()
        await self._store.enqueue(visitor_id, score)
        await self.admit_tick()
        return await self.status(visitor_id)

    async def status(self, visitor_id: str) -> dict[str, object]:
        await self._store.gc_shoppers(self._now())
        shopper = await self._store.get_shopper(visitor_id)
        if shopper is not None and shopper.expires_at > self._now():
            return {
                "state": "admitted",
                "visitor_id": visitor_id,
                "token": shopper.token,
                "expires_at": datetime.fromtimestamp(shopper.expires_at, tz=UTC),
                "position": None,
                "queued": await self._store.queue_size(),
                "admitted": await self._store.shopper_count(self._now()),
            }
        rank = await self._store.rank(visitor_id)
        if rank is None:
            return {
                "state": "unknown",
                "visitor_id": visitor_id,
                "token": None,
                "expires_at": None,
                "position": None,
                "queued": await self._store.queue_size(),
                "admitted": await self._store.shopper_count(self._now()),
            }
        per_second = admits_per_second(self._settings.waiting_room_admit_per_minute)
        position = rank + 1
        return {
            "state": "queued",
            "visitor_id": visitor_id,
            "token": None,
            "expires_at": None,
            "position": position,
            "estimated_wait_seconds": (position + per_second - 1) // per_second,
            "queued": await self._store.queue_size(),
            "admitted": await self._store.shopper_count(self._now()),
        }

    async def stats(self) -> dict[str, int]:
        await self._store.gc_shoppers(self._now())
        return {
            "queued": await self._store.queue_size(),
            "admitted": await self._store.shopper_count(self._now()),
            "admit_per_minute": self._settings.waiting_room_admit_per_minute,
            "bulkhead": self._settings.checkout_concurrency_limit,
        }

    async def visitor_for_token(self, token: str) -> str | None:
        await self._store.gc_shoppers(self._now())
        return await self._store.visitor_for_token(token)

    async def admit_tick(self) -> int:
        now = self._now()
        await self._store.gc_shoppers(now)
        active = await self._store.shopper_count(now)
        bulkhead_slots = max(0, self._settings.checkout_concurrency_limit - active)
        rate_slots = await self._store.take_rate_tokens(
            int(now),
            admits_per_second(self._settings.waiting_room_admit_per_minute),
            bulkhead_slots,
        )
        waiting = await self._store.queue_size()
        n = min(rate_slots, waiting, bulkhead_slots)
        if n <= 0:
            return 0
        admitted = await self._store.pop_front(n)
        ttl = self._settings.shopping_ttl_seconds
        expires_at = now + ttl
        for visitor_id in admitted:
            shopper = Shopper(
                visitor_id=visitor_id,
                token=self._tokens.new_token(),
                expires_at=expires_at,
            )
            await self._store.put_shopper(shopper, ttl)
        return len(admitted)

    def _now(self) -> float:
        return self._clock.now().timestamp()
