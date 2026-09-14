from typing import Protocol
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.catalog.models import GeneralAdmission, Seat, SeatStatus
from arena_onsale.checkout.sql import statement_rowcount
from arena_onsale.inventory.models import GaReservation, Hold, HoldStatus


class InventoryFinalizer(Protocol):
    async def confirm_assigned(self, hold_id: UUID) -> bool:
        """Optimistic HELD → SOLD. False means a version/status conflict."""

    async def confirm_ga(self, reservation_id: UUID) -> bool:
        """Mark the GA reservation confirmed. Pool already decremented."""

    async def release_assigned(self, hold_id: UUID) -> list[UUID]:
        """Return released seat ids. Empty if the hold was not active."""

    async def release_ga(self, reservation_id: UUID) -> bool:
        """Return inventory to the pool. False if the reservation was not active."""


class SqlInventoryFinalizer:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def confirm_assigned(self, hold_id: UUID) -> bool:
        hold = await self._session.get(Hold, hold_id)
        if hold is None or hold.status is not HoldStatus.ACTIVE:
            return False
        seats = list(
            (
                await self._session.execute(
                    select(Seat).where(Seat.hold_id == hold_id).order_by(Seat.id)
                )
            ).scalars()
        )
        if not seats:
            return False
        for seat in seats:
            result = await self._session.execute(
                update(Seat)
                .where(
                    Seat.id == seat.id,
                    Seat.status == SeatStatus.HELD,
                    Seat.version == seat.version,
                    Seat.hold_id == hold_id,
                )
                .values(status=SeatStatus.SOLD, version=seat.version + 1)
            )
            if statement_rowcount(result) != 1:
                return False
        hold.status = HoldStatus.CONFIRMED
        return True

    async def confirm_ga(self, reservation_id: UUID) -> bool:
        reservation = await self._session.get(GaReservation, reservation_id)
        if reservation is None or reservation.status is not HoldStatus.ACTIVE:
            return False
        reservation.status = HoldStatus.CONFIRMED
        return True

    async def release_assigned(self, hold_id: UUID) -> list[UUID]:
        hold = await self._session.get(Hold, hold_id)
        if hold is None or hold.status is not HoldStatus.ACTIVE:
            return []
        seats = list(
            (
                await self._session.execute(
                    select(Seat).where(Seat.hold_id == hold_id).order_by(Seat.id)
                )
            ).scalars()
        )
        released: list[UUID] = []
        for seat in seats:
            result = await self._session.execute(
                update(Seat)
                .where(Seat.id == seat.id, Seat.hold_id == hold_id)
                .values(
                    status=SeatStatus.AVAILABLE,
                    hold_id=None,
                    held_until=None,
                    version=seat.version + 1,
                )
            )
            if statement_rowcount(result) == 1:
                released.append(seat.id)
        hold.status = HoldStatus.EXPIRED
        return released

    async def release_ga(self, reservation_id: UUID) -> bool:
        reservation = await self._session.get(GaReservation, reservation_id)
        if reservation is None or reservation.status is not HoldStatus.ACTIVE:
            return False
        snapshot = await self._session.get(GeneralAdmission, reservation.match_id)
        if snapshot is None:
            return False
        result = await self._session.execute(
            update(GeneralAdmission)
            .where(
                GeneralAdmission.match_id == reservation.match_id,
                GeneralAdmission.version == snapshot.version,
            )
            .values(
                available=GeneralAdmission.available + reservation.quantity,
                version=GeneralAdmission.version + 1,
            )
        )
        if statement_rowcount(result) != 1:
            return False
        reservation.status = HoldStatus.EXPIRED
        return True
