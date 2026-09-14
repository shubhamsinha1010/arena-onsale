import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.catalog.models import Seat
from arena_onsale.checkout.errors import (
    FinalizeFailedError,
    PaymentFailedError,
    ReservationNotActiveError,
    ReservationNotFoundError,
)
from arena_onsale.checkout.finalizer import InventoryFinalizer, SqlInventoryFinalizer
from arena_onsale.checkout.models import (
    Order,
    OrderStatus,
    OutboxEvent,
    Payment,
    PaymentStatus,
)
from arena_onsale.checkout.psp import PaymentProvider
from arena_onsale.inventory.models import GaReservation, Hold, HoldStatus
from arena_onsale.shared.clock import Clock
from arena_onsale.shared.settings import Settings

logger = logging.getLogger("arena_onsale.checkout")


class CheckoutService:
    def __init__(
        self,
        session: AsyncSession,
        psp: PaymentProvider,
        finalizer: InventoryFinalizer,
        clock: Clock,
        settings: Settings,
    ) -> None:
        self._session = session
        self._psp = psp
        self._finalizer = finalizer
        self._clock = clock
        self._settings = settings

    async def get(self, order_id: UUID) -> Order | None:
        return await self._session.get(Order, order_id)

    async def checkout(
        self,
        *,
        session_id: str,
        idempotency_key: str,
        hold_id: UUID | None,
        ga_reservation_id: UUID | None,
    ) -> tuple[Order, bool]:
        if (hold_id is None) == (ga_reservation_id is None):
            raise ReservationNotFoundError
        existing = await self._order_by_key(idempotency_key)
        if existing is not None:
            if existing.session_id != session_id:
                raise ReservationNotActiveError
            if existing.status in {
                OrderStatus.CONFIRMED,
                OrderStatus.PAYMENT_FAILED,
                OrderStatus.COMPENSATED,
            }:
                return existing, False
            resumed = await self._resume(existing)
            return resumed, False

        match_id, amount = await self._quote(hold_id, ga_reservation_id, session_id)
        order = Order(
            match_id=match_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
            hold_id=hold_id,
            ga_reservation_id=ga_reservation_id,
            status=OrderStatus.PAYMENT_PENDING,
            amount_cents=amount,
            version=1,
            created_at=self._clock.now(),
        )
        self._session.add(order)
        await self._session.commit()
        created = await self._resume(order)
        return created, True

    async def _resume(self, order: Order) -> Order:
        payment = await self._ensure_payment(order)
        if payment.status is PaymentStatus.PENDING:
            charge = await self._psp.charge(
                amount_cents=order.amount_cents,
                idempotency_key=payment.idempotency_key,
            )
            if not charge.ok:
                payment.status = PaymentStatus.FAILED
                payment.failure_reason = charge.message
                order.status = OrderStatus.PAYMENT_FAILED
                await self._session.commit()
                raise PaymentFailedError(charge.message or "payment failed")
            payment.status = PaymentStatus.CAPTURED
            payment.psp_ref = charge.psp_ref
            await self._session.commit()
        if payment.status is PaymentStatus.REFUNDED:
            return order
        if order.status is OrderStatus.CONFIRMED:
            return order
        await self._finalize(order, payment)
        return order

    async def _finalize(self, order: Order, payment: Payment) -> None:
        if order.hold_id is not None:
            confirmed = await self._finalizer.confirm_assigned(order.hold_id)
        else:
            assert order.ga_reservation_id is not None
            confirmed = await self._finalizer.confirm_ga(order.ga_reservation_id)
        if not confirmed:
            await self._session.rollback()
            await self._compensate(order, payment)
            raise FinalizeFailedError
        order.status = OrderStatus.CONFIRMED
        order.version += 1
        self._session.add(
            OutboxEvent(
                aggregate_id=order.id,
                event_type="TicketConfirmed",
                payload={"order_id": str(order.id), "match_id": str(order.match_id)},
                created_at=self._clock.now(),
            )
        )
        await self._session.commit()

    async def _compensate(self, order: Order, payment: Payment) -> None:
        if payment.status is PaymentStatus.CAPTURED and payment.psp_ref is not None:
            await self._psp.refund(
                psp_ref=payment.psp_ref,
                idempotency_key=f"refund:{payment.idempotency_key}",
            )
            payment.status = PaymentStatus.REFUNDED
        order.status = OrderStatus.COMPENSATED
        order.version += 1
        self._session.add(
            OutboxEvent(
                aggregate_id=order.id,
                event_type="FinalizeFailed",
                payload={
                    "order_id": str(order.id),
                    "reason": "optimistic_confirm_conflict",
                },
                created_at=self._clock.now(),
            )
        )
        logger.error("finalize failed after capture; refunded order=%s", order.id)
        await self._session.commit()

    async def _quote(
        self,
        hold_id: UUID | None,
        ga_reservation_id: UUID | None,
        session_id: str,
    ) -> tuple[UUID, int]:
        now = self._clock.now()
        if hold_id is not None:
            hold = await self._session.get(Hold, hold_id)
            if hold is None:
                raise ReservationNotFoundError
            if not _usable(hold.status, hold.session_id, hold.expires_at, session_id, now):
                raise ReservationNotActiveError
            count = await self._session.scalar(
                select(func.count()).select_from(Seat).where(Seat.hold_id == hold_id)
            )
            if not count:
                raise ReservationNotActiveError
            return hold.match_id, int(count) * self._settings.ticket_price_cents
        reservation = await self._session.get(GaReservation, ga_reservation_id)
        if reservation is None:
            raise ReservationNotFoundError
        if not _usable(
            reservation.status,
            reservation.session_id,
            reservation.expires_at,
            session_id,
            now,
        ):
            raise ReservationNotActiveError
        return reservation.match_id, reservation.quantity * self._settings.ticket_price_cents

    async def _ensure_payment(self, order: Order) -> Payment:
        result = await self._session.execute(select(Payment).where(Payment.order_id == order.id))
        payment = result.scalar_one_or_none()
        if payment is not None:
            return payment
        payment = Payment(
            order_id=order.id,
            idempotency_key=f"pay:{order.id}",
            status=PaymentStatus.PENDING,
            amount_cents=order.amount_cents,
        )
        self._session.add(payment)
        await self._session.commit()
        return payment

    async def _order_by_key(self, idempotency_key: str) -> Order | None:
        result = await self._session.execute(
            select(Order).where(Order.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()


def _usable(
    status: HoldStatus,
    owner: str,
    expires_at: datetime,
    session_id: str,
    now: datetime,
) -> bool:
    return status is HoldStatus.ACTIVE and owner == session_id and expires_at > now


def checkout_service(
    session: AsyncSession,
    psp: PaymentProvider,
    clock: Clock,
    settings: Settings,
) -> CheckoutService:
    return CheckoutService(session, psp, SqlInventoryFinalizer(session), clock, settings)
