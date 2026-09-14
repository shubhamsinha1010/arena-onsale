import random
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.inventory.errors import GaNotFoundError, GaQuantityError, GaUnavailableError
from arena_onsale.inventory.ga_service import GaReservationService
from arena_onsale.inventory.ga_stock import ClaimOutcome
from arena_onsale.inventory.models import GaReservation
from arena_onsale.inventory.retry import jitter_delay_seconds
from arena_onsale.shared.clock import SystemClock
from arena_onsale.shared.settings import Settings


class _EmptyResult:
    def scalar_one_or_none(self) -> None:
        return None


class StubSession:
    async def execute(self, _stmt: object) -> _EmptyResult:
        return _EmptyResult()

    async def get(self, _entity: object, _pk: object) -> None:
        return None


class RecordingSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.delays.append(seconds)


class InMemoryGaStock:
    def __init__(
        self,
        *,
        available: int | None,
        conflicts: int = 0,
    ) -> None:
        self.available = available
        self.conflicts = conflicts
        self.claims: list[GaReservation] = []

    async def claim(
        self,
        *,
        match_id: object,
        quantity: int,
        reservation: GaReservation,
    ) -> ClaimOutcome:
        del match_id
        if self.available is None:
            return ClaimOutcome.MISSING
        if self.conflicts > 0:
            self.conflicts -= 1
            return ClaimOutcome.CONFLICT
        if self.available < quantity:
            return ClaimOutcome.INSUFFICIENT
        self.available -= quantity
        self.claims.append(reservation)
        return ClaimOutcome.CLAIMED


def _service(
    stock: InMemoryGaStock, sleeper: RecordingSleeper | None = None
) -> GaReservationService:
    return GaReservationService(
        session=cast(AsyncSession, StubSession()),
        stock=stock,
        clock=SystemClock(),
        settings=Settings(),
        sleeper=sleeper or RecordingSleeper(),
        rng=random.Random(0),
    )


def test_jitter_stays_inside_the_documented_window() -> None:
    rng = random.Random(1)
    delays = [jitter_delay_seconds(50, 200, rng) for _ in range(50)]
    assert all(0.05 <= delay <= 0.2 for delay in delays)
    assert len({round(delay, 5) for delay in delays}) > 1


def test_jitter_rejects_an_inverted_window() -> None:
    with pytest.raises(ValueError, match="retry window"):
        jitter_delay_seconds(200, 50, random.Random())


@pytest.mark.asyncio
async def test_version_conflicts_retry_then_succeed() -> None:
    stock = InMemoryGaStock(available=10, conflicts=2)
    sleeper = RecordingSleeper()
    service = _service(stock, sleeper)
    reservation, created = await service.reserve(
        match_id=uuid4(),
        quantity=2,
        session_id="priya",
        idempotency_key="ga-1",
    )
    assert created is True
    assert reservation.quantity == 2
    assert stock.available == 8
    assert len(sleeper.delays) == 2
    assert all(0.05 <= delay <= 0.2 for delay in sleeper.delays)


@pytest.mark.asyncio
async def test_insufficient_stock_does_not_retry() -> None:
    stock = InMemoryGaStock(available=1, conflicts=0)
    sleeper = RecordingSleeper()
    service = _service(stock, sleeper)
    with pytest.raises(GaUnavailableError):
        await service.reserve(
            match_id=uuid4(),
            quantity=2,
            session_id="priya",
            idempotency_key="ga-2",
        )
    assert sleeper.delays == []


@pytest.mark.asyncio
async def test_missing_pool() -> None:
    service = _service(InMemoryGaStock(available=None))
    with pytest.raises(GaNotFoundError):
        await service.reserve(
            match_id=uuid4(),
            quantity=1,
            session_id="priya",
            idempotency_key="ga-3",
        )


@pytest.mark.asyncio
async def test_exhausted_conflicts_look_like_sold_out() -> None:
    stock = InMemoryGaStock(available=10, conflicts=5)
    sleeper = RecordingSleeper()
    service = _service(stock, sleeper)
    with pytest.raises(GaUnavailableError):
        await service.reserve(
            match_id=uuid4(),
            quantity=1,
            session_id="priya",
            idempotency_key="ga-4",
        )
    assert len(sleeper.delays) == 2
    assert stock.available == 10


@pytest.mark.asyncio
async def test_quantity_cap() -> None:
    service = _service(InMemoryGaStock(available=40))
    with pytest.raises(GaQuantityError) as exc:
        await service.reserve(
            match_id=uuid4(),
            quantity=9,
            session_id="priya",
            idempotency_key="ga-5",
        )
    assert exc.value.maximum == 8
