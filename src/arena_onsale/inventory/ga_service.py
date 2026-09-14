import random
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.inventory.errors import (
    GaNotFoundError,
    GaQuantityError,
    GaUnavailableError,
    HoldConflictError,
)
from arena_onsale.inventory.ga_stock import ClaimOutcome, GaStock, SqlGaStock
from arena_onsale.inventory.models import GaReservation, HoldStatus
from arena_onsale.inventory.retry import jitter_delay_seconds
from arena_onsale.shared.clock import Clock
from arena_onsale.shared.retry import AsyncioSleeper, Sleeper
from arena_onsale.shared.settings import Settings


class GaReservationService:
    def __init__(
        self,
        session: AsyncSession,
        stock: GaStock,
        clock: Clock,
        settings: Settings,
        sleeper: Sleeper | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._session = session
        self._stock = stock
        self._clock = clock
        self._settings = settings
        self._sleeper = sleeper or AsyncioSleeper()
        self._rng = rng or random.Random()

    async def get(self, reservation_id: UUID) -> GaReservation | None:
        return await self._session.get(GaReservation, reservation_id)

    async def reserve(
        self,
        *,
        match_id: UUID,
        quantity: int,
        session_id: str,
        idempotency_key: str,
    ) -> tuple[GaReservation, bool]:
        if quantity < 1 or quantity > self._settings.ga_max_quantity:
            raise GaQuantityError(quantity, self._settings.ga_max_quantity)
        existing = await self._existing(idempotency_key)
        if existing is not None:
            if existing.session_id != session_id:
                raise HoldConflictError
            return existing, False

        attempts = self._settings.ga_max_attempts
        for attempt in range(attempts):
            reservation = self._new_reservation(
                match_id=match_id,
                session_id=session_id,
                idempotency_key=idempotency_key,
                quantity=quantity,
            )
            outcome = await self._stock.claim(
                match_id=match_id,
                quantity=quantity,
                reservation=reservation,
            )
            if outcome is ClaimOutcome.CLAIMED:
                return reservation, True
            if outcome is ClaimOutcome.MISSING:
                raise GaNotFoundError
            if outcome is ClaimOutcome.INSUFFICIENT:
                raise GaUnavailableError
            if attempt + 1 < attempts:
                await self._sleeper.sleep(
                    jitter_delay_seconds(
                        self._settings.ga_retry_min_ms,
                        self._settings.ga_retry_max_ms,
                        self._rng,
                    )
                )
        raise GaUnavailableError

    async def _existing(self, idempotency_key: str) -> GaReservation | None:
        result = await self._session.execute(
            select(GaReservation).where(GaReservation.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    def _new_reservation(
        self,
        *,
        match_id: UUID,
        session_id: str,
        idempotency_key: str,
        quantity: int,
    ) -> GaReservation:
        now = self._clock.now()
        return GaReservation(
            match_id=match_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
            quantity=quantity,
            status=HoldStatus.ACTIVE,
            expires_at=now + timedelta(seconds=self._settings.hold_ttl_seconds),
            created_at=now,
        )


def ga_service(
    session: AsyncSession,
    clock: Clock,
    settings: Settings,
    sleeper: Sleeper | None = None,
    rng: random.Random | None = None,
) -> GaReservationService:
    return GaReservationService(
        session,
        SqlGaStock(session),
        clock,
        settings,
        sleeper=sleeper,
        rng=rng,
    )
