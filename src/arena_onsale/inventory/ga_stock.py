from enum import StrEnum
from typing import Protocol
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.catalog.models import GeneralAdmission
from arena_onsale.inventory.models import GaReservation


class ClaimOutcome(StrEnum):
    CLAIMED = "claimed"
    MISSING = "missing"
    INSUFFICIENT = "insufficient"
    CONFLICT = "conflict"


class GaStock(Protocol):
    async def claim(
        self,
        *,
        match_id: UUID,
        quantity: int,
        reservation: GaReservation,
    ) -> ClaimOutcome:
        """Decrement the pool and persist the reservation in one short transaction."""


class SqlGaStock:
    """Optimistic GA counter. No row lock; the version column is the gate."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim(
        self,
        *,
        match_id: UUID,
        quantity: int,
        reservation: GaReservation,
    ) -> ClaimOutcome:
        snapshot = await self._session.scalar(
            select(GeneralAdmission).where(GeneralAdmission.match_id == match_id)
        )
        if snapshot is None:
            await self._session.rollback()
            return ClaimOutcome.MISSING
        if snapshot.available < quantity:
            await self._session.rollback()
            return ClaimOutcome.INSUFFICIENT
        result = await self._session.execute(
            update(GeneralAdmission)
            .where(
                GeneralAdmission.match_id == match_id,
                GeneralAdmission.version == snapshot.version,
                GeneralAdmission.available >= quantity,
            )
            .values(
                available=GeneralAdmission.available - quantity,
                version=GeneralAdmission.version + 1,
            )
        )
        if int(getattr(result, "rowcount", 0) or 0) != 1:
            await self._session.rollback()
            return ClaimOutcome.CONFLICT
        self._session.add(reservation)
        await self._session.commit()
        return ClaimOutcome.CLAIMED
