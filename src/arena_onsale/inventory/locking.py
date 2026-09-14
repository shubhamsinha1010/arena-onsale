from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from arena_onsale.shared.redis import RedisClient

_RELEASE_IF_OWNED = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


def seat_lock_key(match_id: UUID, seat_id: UUID) -> str:
    return f"lock:match:{match_id}:seat:{seat_id}"


def ordered_seat_ids(seat_ids: Sequence[UUID]) -> list[UUID]:
    """Always lock in one order so two multi-seat holds cannot deadlock."""
    return sorted(set(seat_ids))


class SeatLockGate(Protocol):
    async def acquire(self, match_id: UUID, seat_id: UUID, token: str, ttl_seconds: int) -> bool:
        """Return True if this caller now owns the lock."""

    async def release(self, match_id: UUID, seat_id: UUID, token: str) -> None:
        """Drop the lock only if ``token`` still owns it."""


class RedisSeatLockGate:
    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def acquire(self, match_id: UUID, seat_id: UUID, token: str, ttl_seconds: int) -> bool:
        ok = await self._redis.set(
            seat_lock_key(match_id, seat_id),
            token,
            nx=True,
            ex=ttl_seconds,
        )
        return ok is True

    async def release(self, match_id: UUID, seat_id: UUID, token: str) -> None:
        await self._redis.eval(
            _RELEASE_IF_OWNED,
            1,
            seat_lock_key(match_id, seat_id),
            token,
        )


async def acquire_all(
    gate: SeatLockGate,
    *,
    match_id: UUID,
    seat_ids: Sequence[UUID],
    token: str,
    ttl_seconds: int,
) -> list[UUID]:
    """Acquire every seat or release what we took and return the empty list.

    An empty return means at least one seat was already locked. Callers must
    not touch Postgres in that case.
    """
    acquired: list[UUID] = []
    for seat_id in ordered_seat_ids(seat_ids):
        if not await gate.acquire(match_id, seat_id, token, ttl_seconds):
            await release_all(gate, match_id=match_id, seat_ids=acquired, token=token)
            return []
        acquired.append(seat_id)
    return acquired


async def release_all(
    gate: SeatLockGate,
    *,
    match_id: UUID,
    seat_ids: Sequence[UUID],
    token: str,
) -> None:
    for seat_id in seat_ids:
        await gate.release(match_id, seat_id, token)
