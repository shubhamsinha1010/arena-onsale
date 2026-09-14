from uuid import UUID, uuid4

import pytest

from arena_onsale.inventory.locking import (
    acquire_all,
    ordered_seat_ids,
    release_all,
    seat_lock_key,
)


class InMemorySeatLockGate:
    def __init__(self) -> None:
        self.owned: dict[str, str] = {}

    async def acquire(self, match_id: UUID, seat_id: UUID, token: str, ttl_seconds: int) -> bool:
        del ttl_seconds
        key = seat_lock_key(match_id, seat_id)
        if key in self.owned:
            return False
        self.owned[key] = token
        return True

    async def release(self, match_id: UUID, seat_id: UUID, token: str) -> None:
        key = seat_lock_key(match_id, seat_id)
        if self.owned.get(key) == token:
            del self.owned[key]


def test_seat_ids_lock_in_sorted_unique_order() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    ordered = ordered_seat_ids([c, a, b, a])
    assert ordered == sorted({a, b, c})
    assert ordered_seat_ids([b, a]) == ordered_seat_ids([a, b])


@pytest.mark.asyncio
async def test_redis_gate_fails_fast_when_a_seat_is_taken() -> None:
    gate = InMemorySeatLockGate()
    match_id = uuid4()
    first, second = uuid4(), uuid4()
    taken = await acquire_all(
        gate,
        match_id=match_id,
        seat_ids=[first],
        token="fan-a",
        ttl_seconds=600,
    )
    assert taken == [first]
    lost = await acquire_all(
        gate,
        match_id=match_id,
        seat_ids=[second, first],
        token="fan-b",
        ttl_seconds=600,
    )
    assert lost == []
    assert gate.owned == {seat_lock_key(match_id, first): "fan-a"}


@pytest.mark.asyncio
async def test_release_is_compare_and_delete() -> None:
    gate = InMemorySeatLockGate()
    match_id = uuid4()
    seat_id = uuid4()
    await acquire_all(gate, match_id=match_id, seat_ids=[seat_id], token="owner", ttl_seconds=600)
    await release_all(gate, match_id=match_id, seat_ids=[seat_id], token="intruder")
    assert seat_lock_key(match_id, seat_id) in gate.owned
    await release_all(gate, match_id=match_id, seat_ids=[seat_id], token="owner")
    assert gate.owned == {}
