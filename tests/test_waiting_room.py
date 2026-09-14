from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from arena_onsale.shared.settings import Settings
from arena_onsale.waiting_room.keys import admits_per_second
from arena_onsale.waiting_room.memory import InMemoryWaitingRoomStore
from arena_onsale.waiting_room.service import WaitingRoomService


@dataclass
class FrozenClock:
    moment: datetime

    def now(self) -> datetime:
        return self.moment


class SeqTokens:
    def __init__(self) -> None:
        self.n = 0

    def new_token(self) -> str:
        self.n += 1
        return f"tok-{self.n}"


def _service(
    *,
    bulkhead: int = 1,
    admit_per_minute: int = 60,
    ttl: int = 60,
    clock: FrozenClock | None = None,
) -> tuple[WaitingRoomService, FrozenClock]:
    frozen = clock or FrozenClock(datetime(2026, 7, 19, 10, 0, tzinfo=UTC))
    service = WaitingRoomService(
        InMemoryWaitingRoomStore(),
        frozen,
        Settings(
            waiting_room_admit_per_minute=admit_per_minute,
            checkout_concurrency_limit=bulkhead,
            shopping_ttl_seconds=ttl,
        ),
        tokens=SeqTokens(),
    )
    return service, frozen


def test_doc_rate_is_about_eight_hundred_a_second() -> None:
    assert admits_per_second(50_000) == 834


@pytest.mark.asyncio
async def test_first_visitor_is_admitted_when_bulkhead_has_room() -> None:
    service, _clock = _service(bulkhead=1)
    snapshot = await service.join("priya")
    assert snapshot["state"] == "admitted"
    assert snapshot["token"] == "tok-1"


@pytest.mark.asyncio
async def test_bulkhead_keeps_everyone_else_in_line() -> None:
    service, _clock = _service(bulkhead=1)
    await service.join("priya")
    queued = await service.join("rahul")
    assert queued["state"] == "queued"
    assert queued["position"] == 1
    stats = await service.stats()
    assert stats["queued"] == 1
    assert stats["admitted"] == 1


@pytest.mark.asyncio
async def test_join_is_idempotent() -> None:
    service, _clock = _service(bulkhead=2)
    first = await service.join("priya")
    second = await service.join("priya")
    assert first["token"] == second["token"]
    stats = await service.stats()
    assert stats["admitted"] == 1


@pytest.mark.asyncio
async def test_rate_limit_caps_admits_in_the_same_second() -> None:
    service, _clock = _service(bulkhead=10, admit_per_minute=60)
    states = [(await service.join(f"fan-{i}"))["state"] for i in range(5)]
    assert states[0] == "admitted"
    assert states[1:] == ["queued", "queued", "queued", "queued"]


@pytest.mark.asyncio
async def test_expired_shopper_frees_the_bulkhead() -> None:
    service, clock = _service(bulkhead=1, ttl=60)
    await service.join("priya")
    clock.moment = clock.moment + timedelta(seconds=61)
    rahul = await service.join("rahul")
    assert rahul["state"] == "admitted"
    assert await service.visitor_for_token("tok-1") is None
    assert await service.visitor_for_token("tok-2") == "rahul"


@pytest.mark.asyncio
async def test_blank_visitor_is_rejected() -> None:
    service, _clock = _service()
    with pytest.raises(ValueError, match="visitor_id"):
        await service.join("  ")
