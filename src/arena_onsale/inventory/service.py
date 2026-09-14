from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.catalog.models import Seat, SeatStatus
from arena_onsale.inventory.errors import HoldConflictError, SeatUnavailableError
from arena_onsale.inventory.locking import (
    SeatLockGate,
    acquire_all,
    ordered_seat_ids,
    release_all,
)
from arena_onsale.inventory.models import Hold, HoldStatus
from arena_onsale.shared.clock import Clock
from arena_onsale.shared.settings import Settings


class HoldService:
    def __init__(
        self,
        session: AsyncSession,
        gate: SeatLockGate,
        clock: Clock,
        settings: Settings,
    ) -> None:
        self._session = session
        self._gate = gate
        self._clock = clock
        self._settings = settings

    async def get(self, hold_id: UUID) -> Hold | None:
        return await self._session.get(Hold, hold_id)

    async def reserve(
        self,
        *,
        match_id: UUID,
        seat_ids: list[UUID],
        session_id: str,
        idempotency_key: str,
    ) -> tuple[Hold, bool]:
        if not seat_ids:
            raise SeatUnavailableError([])
        existing = await self._existing_hold(idempotency_key)
        if existing is not None:
            if existing.session_id != session_id:
                raise HoldConflictError
            return existing, False

        hold_id = uuid4()
        token = str(hold_id)
        ordered = ordered_seat_ids(seat_ids)
        acquired = await acquire_all(
            self._gate,
            match_id=match_id,
            seat_ids=ordered,
            token=token,
            ttl_seconds=self._settings.hold_ttl_seconds,
        )
        if not acquired:
            raise SeatUnavailableError(ordered)
        try:
            hold = await self._persist_hold(
                hold_id=hold_id,
                match_id=match_id,
                seat_ids=ordered,
                session_id=session_id,
                idempotency_key=idempotency_key,
            )
        except Exception:
            await release_all(self._gate, match_id=match_id, seat_ids=acquired, token=token)
            raise
        return hold, True

    async def _existing_hold(self, idempotency_key: str) -> Hold | None:
        result = await self._session.execute(
            select(Hold).where(Hold.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def _persist_hold(
        self,
        *,
        hold_id: UUID,
        match_id: UUID,
        seat_ids: list[UUID],
        session_id: str,
        idempotency_key: str,
    ) -> Hold:
        result = await self._session.execute(
            select(Seat)
            .where(Seat.id.in_(seat_ids), Seat.match_id == match_id)
            .order_by(Seat.id)
            .with_for_update()
        )
        seats = list(result.scalars())
        if len(seats) != len(seat_ids):
            raise SeatUnavailableError(seat_ids)
        taken = [seat.id for seat in seats if seat.status is not SeatStatus.AVAILABLE]
        if taken:
            raise SeatUnavailableError(taken)

        now = self._clock.now()
        expires_at = now + timedelta(seconds=self._settings.hold_ttl_seconds)
        hold = Hold(
            id=hold_id,
            match_id=match_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
            status=HoldStatus.ACTIVE,
            expires_at=expires_at,
            created_at=now,
        )
        self._session.add(hold)
        await self._session.flush()
        for seat in seats:
            seat.status = SeatStatus.HELD
            seat.hold_id = hold.id
            seat.held_until = expires_at
            seat.version += 1
        await self._session.commit()
        await self._session.refresh(hold)
        return hold

    async def seats_for_hold(self, hold_id: UUID) -> list[Seat]:
        result = await self._session.execute(
            select(Seat).where(Seat.hold_id == hold_id).order_by(Seat.id)
        )
        return list(result.scalars())
