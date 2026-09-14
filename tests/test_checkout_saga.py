from datetime import UTC, datetime
from uuid import uuid4

import pytest

from arena_onsale.checkout.errors import FinalizeFailedError
from arena_onsale.checkout.models import Order, OrderStatus, OutboxEvent, Payment, PaymentStatus
from arena_onsale.checkout.psp import MockPsp
from arena_onsale.checkout.service import CheckoutService
from arena_onsale.shared.clock import SystemClock
from arena_onsale.shared.settings import Settings


class NullSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class FakeFinalizer:
    def __init__(self, *, ok: bool) -> None:
        self.ok = ok

    async def confirm_assigned(self, hold_id: object) -> bool:
        del hold_id
        return self.ok

    async def confirm_ga(self, reservation_id: object) -> bool:
        del reservation_id
        return self.ok

    async def release_assigned(self, hold_id: object) -> list[object]:
        del hold_id
        return []

    async def release_ga(self, reservation_id: object) -> bool:
        del reservation_id
        return True


@pytest.mark.asyncio
async def test_psp_replay_does_not_double_charge() -> None:
    psp = MockPsp()
    first = await psp.charge(amount_cents=15000, idempotency_key="pay_priya_001")
    second = await psp.charge(amount_cents=15000, idempotency_key="pay_priya_001")
    assert first.ok and second.ok
    assert first.psp_ref == second.psp_ref
    assert psp.capture_count == 1


@pytest.mark.asyncio
async def test_psp_refund_is_idempotent() -> None:
    psp = MockPsp()
    charge = await psp.charge(amount_cents=1, idempotency_key="pay-1")
    assert charge.psp_ref is not None
    await psp.refund(psp_ref=charge.psp_ref, idempotency_key="refund:pay-1")
    await psp.refund(psp_ref=charge.psp_ref, idempotency_key="refund:pay-1")
    assert psp.refund_count == 1


@pytest.mark.asyncio
async def test_finalize_conflict_refunds_and_compensates() -> None:
    psp = MockPsp()
    captured = await psp.charge(amount_cents=15000, idempotency_key="pay:order")
    session = NullSession()
    service = CheckoutService(
        session,  # type: ignore[arg-type]
        psp,
        FakeFinalizer(ok=False),  # type: ignore[arg-type]
        SystemClock(),
        Settings(),
    )
    order = Order(
        id=uuid4(),
        match_id=uuid4(),
        session_id="priya",
        idempotency_key="ord-1",
        hold_id=uuid4(),
        status=OrderStatus.PAYMENT_PENDING,
        amount_cents=15000,
        version=1,
        created_at=datetime.now(UTC),
    )
    payment = Payment(
        order_id=order.id,
        idempotency_key="pay:order",
        psp_ref=captured.psp_ref,
        status=PaymentStatus.CAPTURED,
        amount_cents=15000,
    )
    with pytest.raises(FinalizeFailedError):
        await service._finalize(order, payment)
    assert payment.status is PaymentStatus.REFUNDED
    assert order.status is OrderStatus.COMPENSATED
    assert psp.refund_count == 1
    types = [item.event_type for item in session.added if isinstance(item, OutboxEvent)]
    assert "FinalizeFailed" in types


@pytest.mark.asyncio
async def test_finalize_success_emits_ticket_confirmed() -> None:
    psp = MockPsp()
    session = NullSession()
    service = CheckoutService(
        session,  # type: ignore[arg-type]
        psp,
        FakeFinalizer(ok=True),  # type: ignore[arg-type]
        SystemClock(),
        Settings(),
    )
    order = Order(
        id=uuid4(),
        match_id=uuid4(),
        session_id="priya",
        idempotency_key="ord-2",
        hold_id=uuid4(),
        status=OrderStatus.PAYMENT_PENDING,
        amount_cents=15000,
        version=1,
        created_at=datetime.now(UTC),
    )
    payment = Payment(
        order_id=order.id,
        idempotency_key="pay:ord-2",
        psp_ref="psp_ok",
        status=PaymentStatus.CAPTURED,
        amount_cents=15000,
    )
    await service._finalize(order, payment)
    assert order.status is OrderStatus.CONFIRMED
    types = [item.event_type for item in session.added if isinstance(item, OutboxEvent)]
    assert "TicketConfirmed" in types
    assert psp.refund_count == 0
