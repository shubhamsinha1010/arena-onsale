from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.checkout.finalizer import InventoryFinalizer
from arena_onsale.checkout.models import Order, Payment, PaymentStatus
from arena_onsale.inventory.locking import SeatLockGate, release_all
from arena_onsale.inventory.models import GaReservation, Hold, HoldStatus


async def has_captured_payment(
    session: AsyncSession, *, hold_id: UUID | None, ga_id: UUID | None
) -> bool:
    stmt = select(Payment.id).join(Order).where(Payment.status == PaymentStatus.CAPTURED)
    if hold_id is not None:
        stmt = stmt.where(Order.hold_id == hold_id)
    elif ga_id is not None:
        stmt = stmt.where(Order.ga_reservation_id == ga_id)
    else:
        return False
    return (await session.scalar(stmt.limit(1))) is not None


async def expire_holds(
    session: AsyncSession,
    finalizer: InventoryFinalizer,
    gate: SeatLockGate,
    *,
    now: datetime,
    batch_size: int,
) -> int:
    result = await session.execute(
        select(Hold)
        .where(Hold.status == HoldStatus.ACTIVE, Hold.expires_at <= now)
        .order_by(Hold.id)
        .with_for_update(skip_locked=True)
        .limit(batch_size)
    )
    expired = 0
    for hold in result.scalars():
        if await has_captured_payment(session, hold_id=hold.id, ga_id=None):
            continue
        seats = await finalizer.release_assigned(hold.id)
        if seats:
            await release_all(gate, match_id=hold.match_id, seat_ids=seats, token=str(hold.id))
            expired += 1
    return expired


async def expire_ga(
    session: AsyncSession,
    finalizer: InventoryFinalizer,
    *,
    now: datetime,
    batch_size: int,
) -> int:
    result = await session.execute(
        select(GaReservation)
        .where(GaReservation.status == HoldStatus.ACTIVE, GaReservation.expires_at <= now)
        .order_by(GaReservation.id)
        .with_for_update(skip_locked=True)
        .limit(batch_size)
    )
    expired = 0
    for reservation in result.scalars():
        if await has_captured_payment(session, hold_id=None, ga_id=reservation.id):
            continue
        if await finalizer.release_ga(reservation.id):
            expired += 1
    return expired
