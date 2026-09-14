"""Publish committed outbox rows after checkout, never during payment I/O.

TicketConfirmed is the email/QR. FinalizeFailed is the ops alert.
Delivery is at-least-once: SKIP LOCKED, mark published only after deliver,
commit in the worker.
"""

from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arena_onsale.checkout.models import OutboxEvent
from arena_onsale.shared.clock import Clock

logger = logging.getLogger("arena_onsale.outbox")


class TicketNotifier(Protocol):
    async def deliver(self, event: OutboxEvent) -> None:
        """Send the side effect. Raise to retry the row."""


class LogTicketNotifier:
    async def deliver(self, event: OutboxEvent) -> None:
        qr = event.aggregate_id.hex[:12]
        if event.event_type == "TicketConfirmed":
            logger.info("email+qr order=%s qr=%s", event.aggregate_id, qr)
            return
        logger.error("ops alert %s payload=%s", event.event_type, event.payload)


async def publish_outbox(
    session: AsyncSession,
    notifier: TicketNotifier,
    clock: Clock,
    *,
    batch_size: int,
) -> int:
    if batch_size <= 0:
        return 0
    result = await session.execute(
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.created_at, OutboxEvent.id)
        .with_for_update(skip_locked=True)
        .limit(batch_size)
    )
    published = 0
    now = clock.now()
    for event in result.scalars():
        await notifier.deliver(event)
        event.published_at = now
        published += 1
    return published
